from __future__ import annotations

from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional
import time

import numpy as np
from fastapi import FastAPI, Response
from pydantic import BaseModel
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

from runtime_adapter import load_runtime, normalize_export_format, predict

app = FastAPI(title="SilentVoix ML PyTorch Runtime", version="1.0")

# --- Prometheus Metrics ---
ML_INFERENCE_LATENCY = Histogram(
    "ml_inference_latency_seconds",
    "Time spent running inference",
    ["pipeline_stage", "model_id"]
)
ML_CONFIDENCE_SCORE = Histogram(
    "ml_confidence_score",
    "Distribution of confidence scores",
    ["model_id"],
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.99, 1.0]
)
ML_REQUEST_COUNT = Counter(
    "ml_request_count_total",
    "Total ML requests processed",
    ["status", "endpoint"]
)

@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

_TORCH_EXPORT_FORMATS = {"pytorch"}
_MODEL_CACHE: Dict[str, Dict[str, object]] = {}
_CACHE_LOCK = Lock()


class RuntimePayload(BaseModel):
    model_id: str
    model_path: str
    export_format: str
    input_dim: int
    labels: List[str]
    modality: Optional[str] = None
    is_state_dict: bool = False
    has_model_class: bool = False


class PredictPayload(RuntimePayload):
    input_vector: List[float]


def _error(code: str, message: str, retryable: bool = False) -> Dict[str, object]:
    return {"status": "error", "code": code, "message": message, "retryable": retryable}


def _validate_payload(payload: RuntimePayload) -> Optional[Dict[str, object]]:
    fmt = normalize_export_format(payload.export_format)
    if fmt not in _TORCH_EXPORT_FORMATS:
        return _error("UNSUPPORTED_EXPORT_FORMAT", f"Export format '{fmt}' is not supported by pytorch runtime")
    if payload.input_dim <= 0:
        return _error("INPUT_DIM_MISMATCH", "input_dim must be > 0")
    model_path = Path(payload.model_path)
    if not model_path.exists():
        return _error("MODEL_NOT_FOUND", f"Model file not found: {model_path}")
    return None


def _load_cached_runtime(payload: RuntimePayload) -> Dict[str, object]:
    model_path = Path(payload.model_path).resolve()
    mtime = model_path.stat().st_mtime

    with _CACHE_LOCK:
        cached = _MODEL_CACHE.get(payload.model_id)
        if cached and cached.get("mtime") == mtime:
            return cached

    runtime = load_runtime(
        str(model_path), 
        payload.export_format, 
        is_state_dict=payload.is_state_dict, 
        has_model_class=payload.has_model_class
    )
    runtime["mtime"] = mtime

    with _CACHE_LOCK:
        _MODEL_CACHE[payload.model_id] = runtime
    return runtime


def _normalize_probs(raw: np.ndarray) -> np.ndarray:
    work = np.asarray(raw, dtype=np.float32).reshape(-1)
    if work.size == 0:
        raise ValueError("Model returned empty prediction")
    if np.any(~np.isfinite(work)):
        raise ValueError("Model returned non-finite prediction values")
    if np.any(work < 0) or work.sum() <= 0:
        exp = np.exp(work - np.max(work))
        denom = float(np.sum(exp))
        if denom <= 0:
            raise ValueError("Model returned invalid logits for normalization")
        return exp / denom
    return work / float(np.sum(work))


@app.get("/health")
def health() -> Dict[str, str]:
    return {
        "status": "ok",
        "service": "ml-pytorch",
        "runtime": "pytorch",
        "version": "1.0",
    }


@app.post("/v1/runtime-check")
def runtime_check(payload: RuntimePayload):
    validation_error = _validate_payload(payload)
    if validation_error:
        return validation_error

    try:
        runtime = _load_cached_runtime(payload)
        zeros = np.zeros((payload.input_dim,), dtype=np.float32)
        probs = predict(runtime, zeros)
        probs = np.asarray(probs, dtype=np.float32).reshape(-1)
        if probs.size == 0:
            return _error("EMPTY_OUTPUT", "Model runtime-check returned empty output")

        return {
            "status": "success",
            "model_id": payload.model_id,
            "runtime": "pytorch",
            "input_dim": payload.input_dim,
            "output_dim": int(probs.shape[0]),
            "message": "Runtime load and dry-run inference succeeded",
        }
    except FileNotFoundError as exc:
        return _error("MODEL_NOT_FOUND", str(exc))
    except ValueError as exc:
        detail = str(exc)
        if "state_dict" in detail.lower():
            return _error("STATE_DICT_ONLY_ARTIFACT", detail)
        return _error("INVALID_MODEL_ARTIFACT", detail)
    except Exception as exc:
        return _error("RUNTIME_LOAD_FAILED", str(exc), retryable=True)


@app.post("/v1/predict")
def run_predict(payload: PredictPayload):
    start_time = time.time()
    validation_error = _validate_payload(payload)
    if validation_error:
        ML_REQUEST_COUNT.labels(status="error", endpoint="predict").inc()
        return validation_error

    vector = np.asarray(payload.input_vector, dtype=np.float32).reshape(-1)
    if vector.shape[0] != payload.input_dim:
        ML_REQUEST_COUNT.labels(status="error", endpoint="predict").inc()
        return _error("INPUT_DIM_MISMATCH", f"input_vector length mismatch: expected {payload.input_dim}, got {vector.shape[0]}")
    if not np.isfinite(vector).all():
        ML_REQUEST_COUNT.labels(status="error", endpoint="predict").inc()
        return _error("NON_FINITE_INPUT", "input_vector contains non-finite values")

    try:
        runtime = _load_cached_runtime(payload)
        
        # Inference timing
        with ML_INFERENCE_LATENCY.labels(pipeline_stage="pytorch_inference", model_id=payload.model_id).time():
            probs = predict(runtime, vector)
        
        probs = _normalize_probs(probs)

        labels = [str(label) for label in payload.labels]
        if len(labels) != probs.shape[0]:
            n = min(len(labels), probs.shape[0])
            labels = labels[:n]
            probs = probs[:n]

        best_idx = int(np.argmax(probs))
        best_label = labels[best_idx]
        best_confidence = float(probs[best_idx])
        
        # Record confidence
        ML_CONFIDENCE_SCORE.labels(model_id=payload.model_id).observe(best_confidence)
        ML_REQUEST_COUNT.labels(status="success", endpoint="predict").inc()

        prob_map = {labels[i]: float(probs[i]) for i in range(len(labels))}
        top3 = sorted(prob_map.items(), key=lambda item: item[1], reverse=True)[:3]

        return {
            "status": "success",
            "model_id": payload.model_id,
            "prediction": {
                "label": best_label,
                "confidence": best_confidence,
                "probabilities": prob_map,
                "top3": [{"label": label, "confidence": conf} for label, conf in top3],
            },
        }
    except FileNotFoundError as exc:
        ML_REQUEST_COUNT.labels(status="error", endpoint="predict").inc()
        return _error("MODEL_NOT_FOUND", str(exc))
    except ValueError as exc:
        ML_REQUEST_COUNT.labels(status="error", endpoint="predict").inc()
        return _error("RUNTIME_PREDICT_FAILED", str(exc))
    except Exception as exc:
        ML_REQUEST_COUNT.labels(status="error", endpoint="predict").inc()
        return _error("RUNTIME_PREDICT_FAILED", str(exc), retryable=True)
