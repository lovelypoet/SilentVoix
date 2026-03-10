from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.settings import settings
from routes.auth_routes import role_or_internal_dep

router = APIRouter(prefix="/early-fusion", tags=["Early Fusion"])


class EarlyFusionPredictRequest(BaseModel):
    session_id: str = Field(default="default", min_length=1)
    fused_features: Optional[List[float]] = None
    cv_features: Optional[List[float]] = None
    sensor_features: Optional[List[float]] = None


class EarlyFusionResetRequest(BaseModel):
    session_id: str = Field(default="default", min_length=1)


def _worker_enabled() -> bool:
    return bool(settings.USE_EARLY_FUSION_WORKER)


def _worker_base_url() -> str:
    base = str(settings.EARLY_FUSION_WORKER_URL or "").strip().rstrip("/")
    if not base:
        raise HTTPException(status_code=503, detail="Early fusion worker URL is not configured.")
    return base


def _call_worker(method: str, path: str, payload: Dict[str, Any] | None = None) -> Dict[str, Any]:
    if not _worker_enabled():
        raise HTTPException(status_code=503, detail="Early fusion worker is disabled.")
    url = f"{_worker_base_url()}{path}"
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.request(method, url, json=payload)
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="Early fusion worker timed out.") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail=f"Early fusion worker request failed: {exc}") from exc

    if response.status_code >= 400:
        detail = response.text
        try:
            detail = response.json().get("detail") or response.json()
        except Exception:
            pass
        raise HTTPException(status_code=response.status_code, detail=detail)
    return response.json()


@router.get("/health")
def early_fusion_health(_user=Depends(role_or_internal_dep("viewer"))) -> Dict[str, Any]:
    return _call_worker("GET", "/health")


@router.post("/predict")
def early_fusion_predict(
    req: EarlyFusionPredictRequest,
    _user=Depends(role_or_internal_dep("viewer")),
) -> Dict[str, Any]:
    payload = req.model_dump()
    return _call_worker("POST", "/predict", payload)


@router.post("/reset")
def early_fusion_reset(
    req: EarlyFusionResetRequest,
    _user=Depends(role_or_internal_dep("viewer")),
) -> Dict[str, Any]:
    payload = {"session_id": req.session_id, "reset": True}
    return _call_worker("POST", "/predict", payload)
