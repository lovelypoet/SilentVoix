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
from api.routes.auth_routes import role_or_internal_dep
from services.datasets.dataset_service import dataset_service, SCHEMA_DIM_MAP

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

def _with_worker_metadata(base: Dict[str, Any], csv_path: Path) -> Dict[str, Any]:
    sidecar = dataset_service.load_sidecar(csv_path)
    if not sidecar:
        base["worker_validation"] = None
        return base
    
    base["health_flags"] = sorted(set(list(base.get("health_flags", [])) + list(sidecar.get("health_flags", []))))
    base["worker_validation"] = sidecar.get("validation")
    base["worker_job_id"] = sidecar.get("job_id")
    base["operator_review"] = sidecar.get("operator_review")
    base["review_history"] = sidecar.get("review_history", [])
    return base

# --- Routes ---

@router.get("/files")
async def list_csv_files(
    include_archived: bool = Query(False),
    _user=Depends(role_or_internal_dep("admin")),
):
    files = dataset_service.list_datasets(include_archived)
    result = []
    for f in files:
        path = Path(f["path"])
        meta = dataset_service.scan_csv_file(path)
        item = {
            "name": f["name"],
            "scope": f["source"],
            "size_bytes": f["size_bytes"],
            "modified_at": f["modified"],
            **meta
        }
        result.append(_with_worker_metadata(item, path))
    
    # Apply manual order
    order = dataset_service.load_order_store()
    if order:
        pos = {name: idx for idx, name in enumerate(order)}
        result.sort(key=lambda x: pos.get(x["name"], 999999))
        
    return {"status": "success", "files": result}

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
    meta = dataset_service.scan_csv_file(path)
    
    key = f"{req.pipeline}:{req.mode}" + (f":{req.modality}" if req.modality else "")
    store = dataset_service.load_selection_store()
    store[key] = {
        "name": safe_name,
        "scope": scope,
        "schema_id": meta.get("schema_id"),
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
    scope, path, safe_name = dataset_service.resolve_csv_path(name)
    meta = dataset_service.scan_csv_file(path)
    
    rows = []
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i < offset: continue
            if len(rows) >= limit: break
            rows.append(row)
            
    return _with_worker_metadata({
        "status": "success",
        "name": safe_name,
        "rows": rows,
        "header": meta.get("columns"),
        **meta
    }, path)

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
