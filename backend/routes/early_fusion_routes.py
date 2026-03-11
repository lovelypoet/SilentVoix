from __future__ import annotations

from typing import Any, Dict, List, Optional
import logging
import os

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from core.settings import settings
from routes.auth_routes import role_or_internal_dep

router = APIRouter(prefix="/early-fusion", tags=["Early Fusion"])
logger = logging.getLogger("signglove.early_fusion")
_DEBUG_EARLY_FUSION = os.getenv("EARLY_FUSION_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}


def _summarize_vec(vec: Optional[List[float]]) -> Dict[str, float]:
    if not vec:
        return {"len": 0, "zeros": 0, "min": 0.0, "max": 0.0, "mean": 0.0}
    zeros = 0
    min_v = float("inf")
    max_v = float("-inf")
    total = 0.0
    for v in vec:
        num = float(v or 0.0)
        if num == 0.0:
            zeros += 1
        if num < min_v:
            min_v = num
        if num > max_v:
            max_v = num
        total += num
    return {
        "len": len(vec),
        "zeros": zeros,
        "min": min_v if min_v != float("inf") else 0.0,
        "max": max_v if max_v != float("-inf") else 0.0,
        "mean": total / len(vec),
    }


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
def early_fusion_health(_user=Depends(role_or_internal_dep("guest"))) -> Dict[str, Any]:
    return _call_worker("GET", "/health")


@router.post("/predict")
def early_fusion_predict(
    req: EarlyFusionPredictRequest,
    _user=Depends(role_or_internal_dep("guest")),
) -> Dict[str, Any]:
    if _DEBUG_EARLY_FUSION:
        cv_stats = _summarize_vec(req.cv_features)
        sensor_stats = _summarize_vec(req.sensor_features)
        logger.info(
            "early-fusion input session=%s cv=%s sensor=%s",
            req.session_id,
            cv_stats,
            sensor_stats,
        )
    payload = req.model_dump()
    return _call_worker("POST", "/predict", payload)


@router.post("/reset")
def early_fusion_reset(
    req: EarlyFusionResetRequest,
    _user=Depends(role_or_internal_dep("guest")),
) -> Dict[str, Any]:
    payload = {"session_id": req.session_id, "reset": True}
    return _call_worker("POST", "/predict", payload)
