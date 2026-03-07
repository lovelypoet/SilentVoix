from __future__ import annotations

from typing import Any, Dict, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.settings import settings
from routes.auth_routes import role_or_internal_dep

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


@router.get("/health")
def fusion_preprocess_health(_user=Depends(role_or_internal_dep("editor"))) -> Dict[str, Any]:
    return _call_worker("GET", "/health")


@router.post("/jobs/analyze")
def analyze_fusion_csv(req: FusionAnalyzeRequest, _user=Depends(role_or_internal_dep("editor"))) -> Dict[str, Any]:
    return _call_worker("POST", "/v1/jobs/analyze", req.model_dump())


@router.get("/jobs/{job_id}")
def get_fusion_job(job_id: str, _user=Depends(role_or_internal_dep("editor"))) -> Dict[str, Any]:
    return _call_worker("GET", f"/v1/jobs/{job_id}")
