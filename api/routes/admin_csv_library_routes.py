from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
import shutil
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from api.core.settings import settings
from api.routes.auth_routes import role_or_internal_dep, get_current_user_dep
from services.datasets.dataset_service import dataset_service, SCHEMA_DIM_MAP
from celery.result import AsyncResult
from db.models import JobRecord, User
from api.core.database import AsyncSessionLocal
from sqlalchemy import select

router = APIRouter(prefix="/admin/csv-library", tags=["Admin CSV Library"])

MAX_PREVIEW_LIMIT = 500

class DatasetSelectionRequest(BaseModel):
    name: str
    pipeline: str = "early"
    mode: str = "single"
    modality: Optional[str] = None

class DeleteCsvRequest(BaseModel):
    confirm_name: str

class ReviewCsvRequest(BaseModel):
    decision: str
    notes: Optional[str] = None

class CsvOrderRequest(BaseModel):
    names: List[str]

# --- Helpers ---

def get_job_status(job_id: str) -> Dict[str, Any]:
    res = AsyncResult(job_id)
    return {
        "job_id": job_id,
        "status": res.status,
        "result": res.result if res.ready() else None,
        "progress": res.info if not res.ready() else None
    }

async def get_job_record_status(job_id: str) -> Dict[str, Any]:
    """Retrieves job status from both Postgres JobRecord and Celery."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(JobRecord).where(JobRecord.id == job_id))
        job = result.scalars().first()
        
        celery_info = get_job_status(job_id)
        
        if not job:
            return celery_info
            
        return {
            "job_id": job_id,
            "status": job.status,
            "celery_status": celery_info["status"],
            "progress": job.progress,
            "task_type": job.task_type,
            "created_at": job.created_at,
            "started_at": job.started_at,
            "finished_at": job.finished_at,
            "error": job.error_log,
            "result_location": job.result_location
        }

def _with_worker_metadata(base: Dict[str, Any], csv_path: Path) -> Dict[str, Any]:
    """
    Merges base file info with metadata from the worker-generated sidecar.
    This replaces synchronous scanning in the API.
    """
    sidecar = dataset_service.load_sidecar(csv_path)
    
    # Default status if no scan has been performed
    base["scan_status"] = sidecar.get("status", "pending")
    base["worker_job_id"] = sidecar.get("job_id")
    base["processed_at"] = sidecar.get("processed_at")
    
    validation = sidecar.get("validation", {})
    if validation:
        # Override basic info with detailed scan results
        base.update({
            "schema_id": validation.get("schema_id"),
            "modality": validation.get("modality"),
            "hand_mode": validation.get("hand_mode"),
            "feature_dim": validation.get("expected_feature_dim"),
            "row_count": validation.get("row_count"),
            "columns": validation.get("columns"),
            "label_summary": validation.get("label_summary"),
            "health_flags": sorted(set(list(base.get("health_flags", [])) + list(validation.get("health_flags", [])) + list(sidecar.get("health_flags", []))))
        })
    else:
        # Fallback for unscanned files
        base.update({
            "schema_id": "unknown",
            "row_count": 0,
            "columns": [],
            "health_flags": list(set(list(base.get("health_flags", [])) + ["needs_scan"]))
        })

    base["worker_validation"] = validation
    base["dataset_id"] = sidecar.get("dataset_id")
    base["operator_review"] = sidecar.get("operator_review")
    base["review_history"] = sidecar.get("review_history", [])
    
    return base

# --- Routes ---

@router.get("/files")
async def list_csv_files(
    include_archived: bool = Query(False),
    _user=Depends(role_or_internal_dep("admin")),
):
    """
    Returns a list of all CSV datasets. 
    Synchronous scanning is removed; metadata is pulled from worker sidecars.
    """
    files = dataset_service.list_datasets(include_archived)
    result = []
    for f in files:
        path = Path(f["path"])
        item = {
            "name": f["name"],
            "scope": f["source"],
            "size_bytes": f["size_bytes"],
            "modified_at": f["modified"],
            "health_flags": []
        }
        result.append(_with_worker_metadata(item, path))
    
    # Apply manual order
    order = dataset_service.load_order_store()
    if order:
        pos = {name: idx for idx, name in enumerate(order)}
        result.sort(key=lambda x: pos.get(x["name"], 999999))
        
    return {"status": "success", "files": result}

@router.post("/files/scan-all")
async def trigger_all_scans(user: User = Depends(role_or_internal_dep("admin"))):
    """
    Triggers a background scan for all datasets that don't have up-to-date metadata.
    """
    files = dataset_service.list_datasets(include_archived=True)
    job_ids = []
    for f in files:
        job_id = dataset_service.trigger_scan(f["name"], user_id=user.id)
        job_ids.append(job_id)
    return {"status": "success", "triggered_count": len(job_ids), "job_ids": job_ids}

@router.get("/selection")
async def get_selected_dataset(
    pipeline: str = Query("early", pattern="^(early|late)$"),
    mode: str = Query("single", pattern="^(single|dual)$"),
    modality: Optional[str] = Query(None, pattern="^(cv|sensor)$"),
    _user=Depends(role_or_internal_dep("admin")),
):
    store = dataset_service.load_selection_store()
    key = f"{pipeline}:{mode}" + (f":{modality}" if modality else "")
    return {"status": "success", "selection": store.get(key)}

@router.post("/selection")
async def set_selected_dataset(
    req: DatasetSelectionRequest,
    _user=Depends(role_or_internal_dep("admin")),
):
    scope, path, safe_name = dataset_service.resolve_csv_path(req.name)
    sidecar = dataset_service.load_sidecar(path)
    validation = sidecar.get("validation", {})
    
    key = f"{req.pipeline}:{req.mode}" + (f":{req.modality}" if req.modality else "")
    store = dataset_service.load_selection_store()
    store[key] = {
        "name": safe_name,
        "scope": scope,
        "schema_id": validation.get("schema_id", "unknown"),
        "selected_at": datetime.now(timezone.utc).isoformat(),
    }
    dataset_service.save_selection_store(store)
    return {"status": "success", "selection": store[key]}

@router.get("/files/{name:path}/preview")
async def preview_csv_file(
    name: str,
    limit: int = Query(100, ge=1, le=MAX_PREVIEW_LIMIT),
    offset: int = Query(0, ge=0),
    _user=Depends(role_or_internal_dep("admin")),
):
    """
    Returns a preview of the CSV rows. 
    Metadata is pulled from sidecar; if file isn't scanned, it might be incomplete.
    """
    scope, path, safe_name = dataset_service.resolve_csv_path(name)
    
    rows = []
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i < offset: continue
            if len(rows) >= limit: break
            rows.append(row)
            
    base_info = {
        "status": "success",
        "name": safe_name,
        "rows": rows,
        "health_flags": []
    }
    return _with_worker_metadata(base_info, path)

@router.get("/files/{name:path}/download")
async def download_csv_file(name: str, _user=Depends(role_or_internal_dep("admin"))):
    _, path, safe_name = dataset_service.resolve_csv_path(name)
    return FileResponse(path=str(path), filename=Path(safe_name).name)

@router.delete("/files/{name:path}")
async def delete_csv_file(name: str, req: DeleteCsvRequest, _user=Depends(role_or_internal_dep("admin"))):
    _, path, safe_name = dataset_service.resolve_csv_path(name)
    if req.confirm_name != safe_name:
        raise HTTPException(status_code=400, detail="Name confirmation mismatch")
    
    path.unlink()
    dataset_service.sidecar_path(path).unlink(missing_ok=True)
    return {"status": "success", "message": f"Deleted {safe_name}"}

@router.post("/files/{name:path}/scan")
async def trigger_dataset_scan(name: str, user: User = Depends(role_or_internal_dep("admin"))):
    job_id = dataset_service.trigger_scan(name, user_id=user.id)
    return {"status": "success", "job_id": job_id, "message": "Scan task triggered in background"}

@router.get("/jobs/{job_id}")
async def get_dataset_job_status(job_id: str, _user=Depends(role_or_internal_dep("admin"))):
    return {"status": "success", "job": await get_job_record_status(job_id)}
