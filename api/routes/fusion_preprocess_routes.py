from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from api.core.settings import settings
from api.routes.auth_routes import role_or_internal_dep

router = APIRouter(prefix="/fusion-preprocess", tags=["Fusion Preprocess"])


class FusionAnalyzeOptions(BaseModel):
    trim_start_ms: Optional[int] = None
    trim_end_ms: Optional[int] = None
    max_abs_sensor_delta_ms: Optional[float] = None
    require_sensor_match: bool = True
    export_label: str = "processed"
    notes: str = ""


class FusionAnalyzeRequest(BaseModel):
    source_file: str = Field(..., min_length=1)
    csv_text: str = Field(..., min_length=1)
    options: FusionAnalyzeOptions = Field(default_factory=FusionAnalyzeOptions)


class SaveProcessedDatasetRequest(BaseModel):
    file_name: Optional[str] = None


def _worker_enabled() -> bool:
    return bool(settings.USE_FUSION_PREPROCESS_WORKER)


def _worker_base_url() -> str:
    base = str(settings.FUSION_PREPROCESS_WORKER_URL or "").strip().rstrip("/")
    if not base:
        raise HTTPException(status_code=503, detail="Fusion preprocess worker URL is not configured.")
    return base


def _call_worker(method: str, path: str, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    if not _worker_enabled():
        raise HTTPException(status_code=503, detail="Fusion preprocess worker is disabled.")
    url = f"{_worker_base_url()}{path}"
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.request(method, url, json=payload)
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="Fusion preprocess worker timed out.") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail=f"Fusion preprocess worker request failed: {exc}") from exc

    if response.status_code >= 400:
        detail = response.text
        try:
            detail = response.json().get("detail") or response.json()
        except Exception:
            pass
        raise HTTPException(status_code=response.status_code, detail=detail)
    return response.json()


def _call_worker_multipart(
    path: str,
    data: Dict[str, Any],
    files: Dict[str, tuple[str, bytes, str]],
) -> Dict[str, Any]:
    if not _worker_enabled():
        raise HTTPException(status_code=503, detail="Fusion preprocess worker is disabled.")
    url = f"{_worker_base_url()}{path}"
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, data=data, files=files)
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="Fusion preprocess worker timed out.") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail=f"Fusion preprocess worker request failed: {exc}") from exc

    if response.status_code >= 400:
        detail = response.text
        try:
            detail = response.json().get("detail") or response.json()
        except Exception:
            pass
        raise HTTPException(status_code=response.status_code, detail=detail)
    return response.json()


def _csv_library_active_root() -> Path:
    root = Path(settings.DATA_DIR) / "csv_library" / "active"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_output_name(name: str) -> str:
    value = (name or "").strip().replace("\\", "/")
    if not value:
        raise HTTPException(status_code=400, detail="Output filename is required.")
    candidate = Path(value).name
    if candidate in {"", ".", ".."}:
        raise HTTPException(status_code=400, detail="Invalid output filename.")
    if Path(candidate).suffix.lower() != ".csv":
        candidate = f"{candidate}.csv"
    return candidate


def _default_output_name(job: Dict[str, Any], schema_id: str) -> str:
    result = job.get("result") or {}
    metadata = result.get("metadata") or {}
    source_file = str(metadata.get("source_file") or f"{schema_id}.csv")
    crop_rules = metadata.get("crop_rules") or {}
    export_label = str(crop_rules.get("export_label") or "processed").strip().replace(" ", "_")
    source_stem = Path(source_file).stem.replace(" ", "_")
    return _safe_output_name(f"{source_stem}_{export_label}.csv")


def _health_flags_from_metadata(metadata: Dict[str, Any]) -> list[str]:
    flags: list[str] = []
    validation = metadata.get("validation") or {}
    status = str(validation.get("status") or "").strip().lower()
    if status:
        flags.append(f"preprocess_{status}")
    if not validation.get("cv_spike_detected", False):
        flags.append("cv_spike_missing")
    if not validation.get("sensor_spike_detected", False):
        flags.append("sensor_spike_missing")
    for reason in validation.get("reasons") or []:
        if not isinstance(reason, str):
            continue
        normalized = reason.strip().lower().replace(" ", "_")
        normalized = "".join(ch for ch in normalized if ch.isalnum() or ch == "_")
        if normalized:
            flags.append(f"validation_{normalized[:80]}")
    return sorted(set(flags))


@router.get("/health")
def fusion_preprocess_health(_user=Depends(role_or_internal_dep("editor"))) -> Dict[str, Any]:
    return _call_worker("GET", "/health")


@router.post("/jobs/analyze")
def analyze_fusion_csv(req: FusionAnalyzeRequest, _user=Depends(role_or_internal_dep("editor"))) -> Dict[str, Any]:
    return _call_worker("POST", "/v1/jobs/analyze", req.model_dump())


@router.post("/jobs/analyze-upload")
async def analyze_fusion_upload(
    source_file: str = Form(...),
    trim_start_ms: Optional[int] = Form(None),
    trim_end_ms: Optional[int] = Form(None),
    max_abs_sensor_delta_ms: Optional[float] = Form(None),
    require_sensor_match: bool = Form(True),
    export_label: str = Form("processed"),
    notes: str = Form(""),
    csv_file: UploadFile = File(...),
    video_file: Optional[UploadFile] = File(None),
    _user=Depends(role_or_internal_dep("editor")),
) -> Dict[str, Any]:
    csv_bytes = await csv_file.read()
    video_bytes = await video_file.read() if video_file else None
    data = {
        "source_file": source_file,
        "trim_start_ms": "" if trim_start_ms is None else str(trim_start_ms),
        "trim_end_ms": "" if trim_end_ms is None else str(trim_end_ms),
        "max_abs_sensor_delta_ms": "" if max_abs_sensor_delta_ms is None else str(max_abs_sensor_delta_ms),
        "require_sensor_match": "true" if require_sensor_match else "false",
        "export_label": export_label,
        "notes": notes,
    }
    files = {
        "csv_file": (csv_file.filename or "capture.csv", csv_bytes, csv_file.content_type or "text/csv"),
    }
    if video_file and video_bytes is not None:
        files["video_file"] = (
            video_file.filename or "capture.webm",
            video_bytes,
            video_file.content_type or "video/webm",
        )
    return _call_worker_multipart("/v1/jobs/analyze-upload", data=data, files=files)


@router.get("/jobs/{job_id}")
def get_fusion_job(job_id: str, _user=Depends(role_or_internal_dep("editor"))) -> Dict[str, Any]:
    return _call_worker("GET", f"/v1/jobs/{job_id}")


@router.post("/jobs/{job_id}/save")
def save_fusion_job_output(
    job_id: str,
    req: SaveProcessedDatasetRequest,
    _user=Depends(role_or_internal_dep("editor")),
) -> Dict[str, Any]:
    job = _call_worker("GET", f"/v1/jobs/{job_id}")
    if str(job.get("status") or "").lower() != "completed":
        raise HTTPException(status_code=409, detail="Only completed preprocess jobs can be saved.")

    result = job.get("result") or {}
    metadata = result.get("metadata") or {}
    processed_csv_text = str(result.get("processed_csv_text") or "")
    schema_id = str(metadata.get("schema_id") or "").strip()

    if not processed_csv_text:
        raise HTTPException(status_code=400, detail="Processed CSV output is empty.")
    if schema_id not in {"fusion_single", "fusion_dual"}:
        raise HTTPException(status_code=400, detail=f"Unsupported fusion schema for save: {schema_id or 'unknown'}")

    target_dir = _csv_library_active_root() / schema_id
    target_dir.mkdir(parents=True, exist_ok=True)

    output_name = _safe_output_name(req.file_name) if req.file_name else _default_output_name(job, schema_id)
    csv_path = target_dir / output_name
    csv_path.write_text(processed_csv_text, encoding="utf-8")

    metadata_path = csv_path.with_suffix(".metadata.json")
    metadata_to_save = {
        **metadata,
        "job_id": job_id,
        "saved_csv_path": str(csv_path),
        "health_flags": _health_flags_from_metadata(metadata),
    }
    metadata_path.write_text(json.dumps(metadata_to_save, ensure_ascii=True, indent=2), encoding="utf-8")

    return {
        "status": "success",
        "job_id": job_id,
        "schema_id": schema_id,
        "saved_name": output_name,
        "csv_path": str(csv_path),
        "metadata_path": str(metadata_path),
        "health_flags": metadata_to_save["health_flags"],
        "validation": metadata.get("validation") or {},
    }
