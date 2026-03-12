from __future__ import annotations

import logging
import os
import time
from collections import deque
from typing import Any, Dict, List, Optional

import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from AI.pipelines.early_fusion_preprocess import (
    build_fused_frame,
    pad_or_trim,
    normalize_sensor,
    summarize_vector,
    SENSOR_ORDER_IMU_FLEX,
    SENSOR_ORDER_FLEX_IMU,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
logger = logging.getLogger("worker-early-fusion")

app = FastAPI(title="SilentVoix Early Fusion Worker", version="0.1")

SEQUENCE_LENGTH = int(os.getenv("EARLY_FUSION_SEQUENCE_LENGTH", "30"))
FEATURE_DIM = int(os.getenv("EARLY_FUSION_FEATURE_DIM", "74"))
LABELS = [l.strip() for l in os.getenv("EARLY_FUSION_LABELS", "").split(",") if l.strip()]
MODEL_PATH = os.getenv("EARLY_FUSION_MODEL_PATH", "")
SENSOR_ORDER = os.getenv("EARLY_FUSION_SENSOR_ORDER", SENSOR_ORDER_IMU_FLEX)
DEBUG_INPUTS = os.getenv("EARLY_FUSION_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}

BUFFER_TTL_SECONDS = int(os.getenv("EARLY_FUSION_BUFFER_TTL_SECONDS", "30"))

_buffers: Dict[str, deque] = {}
_last_seen: Dict[str, float] = {}
_model = None


class PredictRequest(BaseModel):
    session_id: str = Field(default="default", min_length=1)
    fused_features: Optional[List[float]] = None
    cv_features: Optional[List[float]] = None
    sensor_features: Optional[List[float]] = None
    cv_landmarks: Optional[List[Any]] = None
    sensor_values: Optional[List[float]] = None
    reset: bool = False


def _get_model():
    global _model
    if _model is not None:
        return _model
    if not MODEL_PATH:
        raise RuntimeError("EARLY_FUSION_MODEL_PATH is not set")
    try:
        import tensorflow as tf  # type: ignore
    except Exception as exc:
        raise RuntimeError(f"TensorFlow is not available: {exc}") from exc
    _model = tf.keras.models.load_model(MODEL_PATH)
    logger.info("Loaded early fusion model from %s", MODEL_PATH)
    return _model


@app.on_event("startup")
def _warm_load_model() -> None:
    if not MODEL_PATH:
        logger.warning("EARLY_FUSION_MODEL_PATH is not set; skipping warm load.")
        return
    try:
        _get_model()
    except Exception as exc:
        logger.warning("Early fusion model warm load failed: %s", exc)


def _cleanup_buffers(now: float) -> None:
    stale = [sid for sid, ts in _last_seen.items() if now - ts > BUFFER_TTL_SECONDS]
    for sid in stale:
        _buffers.pop(sid, None)
        _last_seen.pop(sid, None)


def _coerce_feature_vec(req: PredictRequest) -> np.ndarray:
    if req.fused_features is not None:
        vec = np.asarray(pad_or_trim(req.fused_features, FEATURE_DIM), dtype=np.float32)
        return vec

    if req.cv_features is not None and req.sensor_features is not None:
        sensor = normalize_sensor(req.sensor_features, dim=11, order=SENSOR_ORDER)
        fused = pad_or_trim(req.cv_features + sensor, FEATURE_DIM)
        return np.asarray(fused, dtype=np.float32)

    if req.cv_landmarks is not None and req.sensor_values is not None:
        vec = build_fused_frame(
            req.cv_landmarks,
            req.sensor_values,
            FEATURE_DIM,
            sensor_dim=11,
            sensor_order=SENSOR_ORDER,
        )
        return vec

    raise HTTPException(
        status_code=400,
        detail="Provide fused_features, (cv_features + sensor_features), or (cv_landmarks + sensor_values)"
    )


@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "sequence_length": SEQUENCE_LENGTH,
        "feature_dim": FEATURE_DIM,
        "labels": LABELS,
        "model_loaded": bool(_model)
    }


@app.post("/predict")
def predict(req: PredictRequest) -> Dict[str, Any]:
    now = time.time()
    _cleanup_buffers(now)

    if req.reset:
        _buffers.pop(req.session_id, None)
        _last_seen.pop(req.session_id, None)
        return {"status": "success", "message": "buffer reset"}

    vec = _coerce_feature_vec(req)
    if not np.all(np.isfinite(vec)):
        raise HTTPException(status_code=400, detail="Invalid input vector: contains NaN/Inf")
    buf = _buffers.setdefault(req.session_id, deque(maxlen=SEQUENCE_LENGTH))
    buf.append(vec)
    _last_seen[req.session_id] = now

    if len(buf) < SEQUENCE_LENGTH:
        payload: Dict[str, Any] = {
            "status": "waiting",
            "buffer_status": f"{len(buf)}/{SEQUENCE_LENGTH}"
        }
        if DEBUG_INPUTS:
            payload["input_stats"] = summarize_vector(vec.tolist())
            payload["sensor_order"] = SENSOR_ORDER
        return payload

    try:
        model = _get_model()
        seq = np.array(list(buf), dtype=np.float32)[None, ...]
        logits = model.predict(seq, verbose=0)
        probs = np.squeeze(logits)
        if probs.ndim != 1:
            probs = probs[0]
        idx = int(np.argmax(probs))
        label = LABELS[idx] if idx < len(LABELS) else str(idx)
        payload: Dict[str, Any] = {
            "status": "success",
            "gesture": label,
            "confidence": float(probs[idx]),
            "buffer_status": f"{len(buf)}/{SEQUENCE_LENGTH}"
        }
        if DEBUG_INPUTS:
            payload["input_stats"] = summarize_vector(vec.tolist())
            payload["sensor_order"] = SENSOR_ORDER
        return payload
    except Exception as exc:
        logger.error("Prediction failed: %s", exc)
        return {"status": "error", "detail": str(exc)}
