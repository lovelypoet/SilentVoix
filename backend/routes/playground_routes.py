from __future__ import annotations

import json
import logging
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

import httpx
import numpy as np
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from AI.runtime_adapter import (
    SUPPORTED_EXPORT_FORMATS,
    SUPPORTED_MODEL_EXTENSIONS,
    load_runtime,
    normalize_export_format,
    predict as predict_runtime,
    validate_export_and_extension,
)
from core.settings import settings
from routes.auth_routes import role_or_internal_dep

router = APIRouter(prefix="/playground", tags=["Realtime AI Playground"])
logger = logging.getLogger("signglove.playground")

ALLOWED_MODEL_EXTENSIONS = SUPPORTED_MODEL_EXTENSIONS
ALLOWED_EXPORT_FORMATS = SUPPORTED_EXPORT_FORMATS
ALLOWED_MODALITIES = {"cv", "sensor"}
MODEL_CACHE_LOCK = threading.Lock()
MODEL_CACHE: Dict[str, Dict[str, Any]] = {}
REMOTE_MODEL_LIBRARY_ROOT = Path("/shared/model_library")


class PlaygroundPredictRequest(BaseModel):
    cv_values: List[float]
    model_id: Optional[str] = None


class PlaygroundSensorPredictRequest(BaseModel):
    sensor_values: List[float]
    model_id: Optional[str] = None


def _models_root() -> Path:
    root = Path(settings.MODEL_LIBRARY_DIR)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _registry_path() -> Path:
    return _models_root() / "registry.json"


def _load_registry() -> Dict[str, Any]:
    path = _registry_path()
    if not path.exists():
        return {"models": [], "active_model_id": None}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"models": [], "active_model_id": None}
        if "models" not in data or not isinstance(data["models"], list):
            data["models"] = []
        if "active_model_id" not in data:
            data["active_model_id"] = None
        changed = False
        root = _models_root().resolve()
        for entry in data["models"]:
            if not isinstance(entry, dict):
                continue
            model_id = str(entry.get("id") or "").strip()
            if model_id:
                model_dir = root / model_id
                model_file_name = str(entry.get("model_file_name") or "").strip()
                current_model_path = str(entry.get("model_path") or "").strip()
                current_model_suffix = Path(current_model_path).suffix.lower()
                file_name_suffix = Path(model_file_name).suffix.lower()
                suffix = file_name_suffix or current_model_suffix or ".bin"
                normalized_model_path = model_dir / f"model{suffix}"
                normalized_metadata_path = model_dir / "metadata.json"
                if str(entry.get("model_path") or "") != str(normalized_model_path):
                    entry["model_path"] = str(normalized_model_path)
                    changed = True
                if str(entry.get("metadata_path") or "") != str(normalized_metadata_path):
                    entry["metadata_path"] = str(normalized_metadata_path)
                    changed = True
            metadata = entry.get("metadata")
            if not isinstance(metadata, dict):
                continue
            if metadata.get("modality"):
                continue
            input_dim = int(entry.get("input_dim") or 0)
            inferred = _infer_modality_from_dim(input_dim)
            if inferred:
                metadata["modality"] = inferred
                input_spec = metadata.get("input_spec")
                if isinstance(input_spec, dict):
                    input_spec["modality"] = inferred
                changed = True
        if changed:
            _save_registry(data)
        return data
    except Exception:
        return {"models": [], "active_model_id": None}


def _save_registry(data: Dict[str, Any]) -> None:
    path = _registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".json.tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=True, indent=2)
    tmp_path.replace(path)


def _get_model_entry(registry: Dict[str, Any], model_id: str) -> Dict[str, Any]:
    entry = next((m for m in registry.get("models", []) if m.get("id") == model_id), None)
    if not entry:
        raise HTTPException(status_code=404, detail=f"Model not found: {model_id}")
    return entry


def _safe_model_artifact_path(entry: Dict[str, Any], field_name: str) -> Path:
    raw = entry.get(field_name)
    if not raw:
        raise HTTPException(status_code=404, detail=f"Artifact missing: {field_name}")
    path = Path(str(raw)).resolve()
    root = _models_root().resolve()
    try:
        path.relative_to(root)
    except ValueError:
        raise HTTPException(status_code=400, detail="Artifact path is outside playground model storage")
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail=f"Artifact file not found: {path.name}")
    return path


def _parse_metadata_bytes(raw: bytes) -> Dict[str, Any]:
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid metadata JSON file")
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=400, detail="Metadata must be a JSON object")
    return parsed


def _validate_metadata(metadata: Dict[str, Any], model_suffix: str) -> None:
    required = ["model_name", "model_family", "input_spec", "labels", "export_format", "version", "precision", "recall", "f1"]
    missing = [key for key in required if key not in metadata]
    if missing:
        raise HTTPException(status_code=400, detail=f"Metadata missing required fields: {', '.join(missing)}")
    if not isinstance(metadata.get("labels"), list) or not metadata["labels"]:
        raise HTTPException(status_code=400, detail="metadata.labels must be a non-empty array")
    if not isinstance(metadata.get("input_spec"), dict):
        raise HTTPException(status_code=400, detail="metadata.input_spec must be an object")
    for metric_name in ("precision", "recall", "f1"):
        if not isinstance(metadata.get(metric_name), (int, float)):
            raise HTTPException(status_code=400, detail=f"metadata.{metric_name} must be numeric")
    export_format = str(metadata.get("export_format", "")).strip().lower()
    try:
        validate_export_and_extension(model_suffix, export_format)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _input_dim_from_metadata(metadata: Dict[str, Any]) -> int:
    input_spec = metadata.get("input_spec") or {}
    if not isinstance(input_spec, dict):
        raise HTTPException(status_code=400, detail="metadata.input_spec must be object")

    # Preferred explicit dim.
    dim = input_spec.get("input_dim")
    if isinstance(dim, (int, float)) and int(dim) > 0:
        return int(dim)

    # Fallback: infer from shape.
    shape = input_spec.get("shape")
    if isinstance(shape, list) and shape:
        for value in reversed(shape):
            if isinstance(value, (int, float)) and int(value) > 0:
                return int(value)

    raise HTTPException(status_code=400, detail="Unable to infer input dimension from metadata.input_spec")


def _infer_modality_from_dim(input_dim: int) -> Optional[str]:
    if input_dim in {63, 126}:
        return "cv"
    if input_dim in {11, 22}:
        return "sensor"
    return None


def _resolve_model_modality(metadata: Dict[str, Any], input_dim: int) -> Optional[str]:
    input_spec = metadata.get("input_spec") or {}
    raw = metadata.get("modality") or input_spec.get("modality")
    if raw is not None:
        modality = str(raw).strip().lower()
        if modality not in ALLOWED_MODALITIES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported modality: {modality}. Allowed: cv, sensor",
            )
        return modality
    return _infer_modality_from_dim(input_dim)


def _entry_modality(entry: Dict[str, Any]) -> str:
    metadata = entry.get("metadata") or {}
    raw = str(metadata.get("modality") or "").strip().lower()
    if raw in ALLOWED_MODALITIES:
        return raw
    inferred = _infer_modality_from_dim(int(entry.get("input_dim") or 0))
    return inferred or ""


def _uses_runtime_services() -> bool:
    return bool(settings.USE_RUNTIME_SERVICES)


def _uses_worker_library() -> bool:
    return bool(settings.USE_WORKER_LIBRARY)


def _trigger_worker_reconcile(reason: str) -> None:
    if not _uses_worker_library():
        return
    base = str(settings.WORKER_LIBRARY_URL).rstrip("/")
    url = f"{base}/v1/reconcile"
    payload = {"apply": True, "prune_missing": False, "activate_fallback": True}
    try:
        resp = httpx.post(url, json=payload, timeout=2.5)
        if resp.status_code >= 400:
            logger.warning("Worker reconcile returned HTTP %s after %s", resp.status_code, reason)
            return
        logger.info("Worker reconcile triggered after %s", reason)
    except Exception as exc:
        logger.warning("Worker reconcile request failed after %s: %s", reason, exc)


def _runtime_service_url(export_format: str) -> str:
    normalized = normalize_export_format(export_format)
    if normalized in {"tflite", "keras", "h5"}:
        return str(settings.ML_TENSORFLOW_URL).rstrip("/")
    if normalized == "pytorch":
        return str(settings.ML_PYTORCH_URL).rstrip("/")
    raise HTTPException(status_code=400, detail=f"Unsupported export format: {export_format}")


def _runtime_service_model_path(entry: Dict[str, Any]) -> str:
    local_path = Path(str(entry.get("model_path", ""))).resolve()
    root = _models_root().resolve()
    try:
        rel = local_path.relative_to(root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Model path is outside model library root") from exc
    return str(REMOTE_MODEL_LIBRARY_ROOT / rel)


def _runtime_payload(entry: Dict[str, Any], input_vector: Optional[np.ndarray] = None) -> Dict[str, Any]:
    metadata = entry.get("metadata", {}) or {}
    payload: Dict[str, Any] = {
        "model_id": str(entry.get("id", "")),
        "model_path": _runtime_service_model_path(entry),
        "export_format": str(metadata.get("export_format", "")),
        "input_dim": int(entry.get("input_dim") or 0),
        "labels": [str(v) for v in (metadata.get("labels") or [])],
        "modality": _entry_modality(entry) or None,
    }
    if input_vector is not None:
        payload["input_vector"] = [float(v) for v in input_vector.tolist()]
    return payload


def _call_runtime_service(entry: Dict[str, Any], endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    service_url = _runtime_service_url(str(entry.get("metadata", {}).get("export_format", "")))
    url = f"{service_url}{endpoint}"
    try:
        resp = httpx.post(url, json=payload, timeout=10.0)
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail=f"Runtime service timeout: {service_url}") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Runtime service request failed: {service_url}") from exc

    try:
        data = resp.json()
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Runtime service returned invalid JSON") from exc

    if resp.status_code >= 400:
        detail = data.get("message") if isinstance(data, dict) else f"Runtime service HTTP {resp.status_code}"
        raise HTTPException(status_code=502, detail=str(detail))
    if isinstance(data, dict) and data.get("status") == "error":
        code = str(data.get("code", "")).strip().upper()
        detail = str(data.get("message") or "Runtime service returned an error")
        if code in {
            "MODEL_NOT_FOUND",
            "UNSUPPORTED_EXPORT_FORMAT",
            "INVALID_MODEL_ARTIFACT",
            "STATE_DICT_ONLY_ARTIFACT",
            "INPUT_DIM_MISMATCH",
            "NON_FINITE_INPUT",
            "EMPTY_OUTPUT",
            "NON_FINITE_OUTPUT",
        }:
            raise HTTPException(status_code=400, detail=detail)
        raise HTTPException(status_code=502, detail=detail)
    if not isinstance(data, dict):
        raise HTTPException(status_code=502, detail="Runtime service response is not an object")
    return data


def _remote_runtime_check(entry: Dict[str, Any]) -> Dict[str, Any]:
    payload = _runtime_payload(entry)
    return _call_runtime_service(entry, "/v1/runtime-check", payload)


def _remote_predict(entry: Dict[str, Any], vector: np.ndarray) -> Dict[str, Any]:
    payload = _runtime_payload(entry, input_vector=vector)
    return _call_runtime_service(entry, "/v1/predict", payload)


def _load_model_runtime(model_entry: Dict[str, Any]) -> Dict[str, Any]:
    model_path = Path(model_entry["model_path"]).resolve()
    if not model_path.exists():
        raise HTTPException(status_code=404, detail=f"Model file not found: {model_path.name}")

    model_id = str(model_entry["id"])
    model_mtime = model_path.stat().st_mtime
    with MODEL_CACHE_LOCK:
        cached = MODEL_CACHE.get(model_id)
        if cached and cached.get("mtime") == model_mtime:
            return cached

    export_format = str(model_entry["metadata"]["export_format"]).lower()
    try:
        runtime: Dict[str, Any] = load_runtime(str(model_path), export_format)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load model runtime: {exc}") from exc
    runtime["mtime"] = model_mtime
    runtime["export_format"] = normalize_export_format(export_format)

    with MODEL_CACHE_LOCK:
        MODEL_CACHE[model_id] = runtime
    return runtime


def _predict_with_runtime(runtime: Dict[str, Any], cv_values: np.ndarray) -> np.ndarray:
    try:
        return predict_runtime(runtime, cv_values)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Runtime prediction failed: {exc}") from exc


def _coerce_input_vector(values: List[float], expected_dim: int, field_name: str) -> np.ndarray:
    vector = np.asarray(values, dtype=np.float32).reshape(-1)
    if expected_dim <= 0:
        raise HTTPException(status_code=500, detail="Invalid model input dimension")
    if vector.shape[0] != expected_dim:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} length mismatch: expected {expected_dim}, got {vector.shape[0]}",
        )
    if not np.isfinite(vector).all():
        raise HTTPException(status_code=400, detail=f"{field_name} contains non-finite values")
    return vector


def _normalize_probs(probs: np.ndarray) -> np.ndarray:
    work = np.asarray(probs, dtype=np.float32).reshape(-1)
    if work.size == 0:
        raise HTTPException(status_code=500, detail="Model returned empty prediction")
    if np.any(~np.isfinite(work)):
        raise HTTPException(status_code=500, detail="Model returned non-finite prediction values")
    if np.any(work < 0) or work.sum() <= 0:
        exp = np.exp(work - np.max(work))
        denom = float(np.sum(exp))
        if denom <= 0:
            raise HTTPException(status_code=500, detail="Model returned invalid logits for normalization")
        return exp / denom
    total = float(np.sum(work))
    if total <= 0:
        raise HTTPException(status_code=500, detail="Model returned invalid probability sum")
    return work / total


def _runtime_status_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _perform_runtime_check(entry: Dict[str, Any]) -> Dict[str, Any]:
    expected_dim = int(entry.get("input_dim") or 0)
    if expected_dim <= 0:
        raise HTTPException(status_code=400, detail="Invalid model input dimension")

    if _uses_runtime_services():
        result = _remote_runtime_check(entry)
        output_dim = int(result.get("output_dim") or 0)
        if output_dim <= 0:
            raise HTTPException(status_code=502, detail="Runtime service returned invalid output dimension")
        return {
            "status": "success",
            "model_id": str(entry.get("id", "")),
            "model_name": entry.get("display_name"),
            "export_format": str(entry.get("metadata", {}).get("export_format", "")),
            "input_dim": expected_dim,
            "output_dim": output_dim,
            "message": str(result.get("message") or "Runtime load and dry-run inference succeeded"),
        }

    runtime = _load_model_runtime(entry)
    probe = np.zeros((expected_dim,), dtype=np.float32)
    probs = _predict_with_runtime(runtime, probe)
    probs = np.asarray(probs, dtype=np.float32).reshape(-1)
    if probs.size == 0:
        raise HTTPException(status_code=500, detail="Model runtime-check returned empty output")

    return {
        "status": "success",
        "model_id": str(entry.get("id", "")),
        "model_name": entry.get("display_name"),
        "export_format": str(entry.get("metadata", {}).get("export_format", "")),
        "input_dim": expected_dim,
        "output_dim": int(probs.shape[0]),
        "message": "Runtime load and dry-run inference succeeded",
    }


def _compute_runtime_status(entry: Dict[str, Any]) -> Dict[str, Any]:
    try:
        result = _perform_runtime_check(entry)
        return {
            "state": "pass",
            "checked_at": _runtime_status_timestamp(),
            "input_dim": int(result["input_dim"]),
            "output_dim": int(result["output_dim"]),
            "message": str(result["message"]),
        }
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        return {
            "state": "fail",
            "checked_at": _runtime_status_timestamp(),
            "message": detail,
        }


@router.post("/models/upload")
async def upload_playground_model(
    model_file: UploadFile = File(...),
    metadata_file: UploadFile = File(...),
    _user=Depends(role_or_internal_dep("editor")),
):
    model_name = Path(model_file.filename or "").name
    metadata_name = Path(metadata_file.filename or "").name
    if not model_name:
        raise HTTPException(status_code=400, detail="model_file is required")
    if not metadata_name.lower().endswith(".json"):
        raise HTTPException(status_code=400, detail="metadata_file must be a .json file")

    suffix = Path(model_name).suffix.lower()
    model_bytes = await model_file.read()
    metadata_bytes = await metadata_file.read()
    if not model_bytes:
        raise HTTPException(status_code=400, detail="Uploaded model file is empty")
    if not metadata_bytes:
        raise HTTPException(status_code=400, detail="Uploaded metadata file is empty")

    metadata = _parse_metadata_bytes(metadata_bytes)
    _validate_metadata(metadata, suffix)
    input_dim = _input_dim_from_metadata(metadata)
    modality = _resolve_model_modality(metadata, input_dim)
    if modality:
        metadata["modality"] = modality
        metadata.setdefault("input_spec", {})
        if isinstance(metadata["input_spec"], dict):
            metadata["input_spec"]["modality"] = modality

    model_id = str(uuid4())
    model_dir = _models_root() / model_id
    model_dir.mkdir(parents=True, exist_ok=True)
    saved_model_path = model_dir / f"model{suffix}"
    saved_metadata_path = model_dir / "metadata.json"
    saved_model_path.write_bytes(model_bytes)
    saved_metadata_path.write_bytes(metadata_bytes)

    now = datetime.now(timezone.utc).isoformat()
    entry = {
        "id": model_id,
        "display_name": str(metadata["model_name"]),
        "model_file_name": model_name,
        "metadata_file_name": metadata_name,
        "model_path": str(saved_model_path),
        "metadata_path": str(saved_metadata_path),
        "metadata": metadata,
        "input_dim": input_dim,
        "created_at": now,
    }
    entry["runtime_status"] = _compute_runtime_status(entry)

    registry = _load_registry()
    registry["models"] = [*registry.get("models", []), entry]
    registry["active_model_id"] = model_id
    _save_registry(registry)
    with MODEL_CACHE_LOCK:
        MODEL_CACHE.pop(model_id, None)
    _trigger_worker_reconcile("model upload")

    return {
        "status": "success",
        "model": entry,
        "active_model_id": model_id,
        "message": "Model uploaded and set as active",
    }


@router.get("/models")
async def list_playground_models(_user=Depends(role_or_internal_dep("editor"))):
    registry = _load_registry()
    return {
        "status": "success",
        "models": registry.get("models", []),
        "active_model_id": registry.get("active_model_id"),
    }


@router.get("/models/active")
async def get_active_playground_model(_user=Depends(role_or_internal_dep("editor"))):
    registry = _load_registry()
    active_id = registry.get("active_model_id")
    active = next((m for m in registry.get("models", []) if m.get("id") == active_id), None)
    return {
        "status": "success",
        "active_model_id": active_id,
        "model": active,
    }


@router.post("/models/{model_id}/activate")
async def activate_playground_model(model_id: str, _user=Depends(role_or_internal_dep("editor"))):
    registry = _load_registry()
    target = _get_model_entry(registry, model_id)
    registry["active_model_id"] = model_id
    target["runtime_status"] = _compute_runtime_status(target)
    _save_registry(registry)
    _trigger_worker_reconcile("model activate")
    return {
        "status": "success",
        "active_model_id": model_id,
        "model": target,
    }


@router.get("/models/{model_id}/download")
async def download_playground_model_artifact(
    model_id: str,
    kind: str = Query("model", pattern="^(model|metadata)$"),
    _user=Depends(role_or_internal_dep("editor")),
):
    registry = _load_registry()
    entry = _get_model_entry(registry, model_id)
    field_name = "model_path" if kind == "model" else "metadata_path"
    file_path = _safe_model_artifact_path(entry, field_name)
    media_type = "application/octet-stream"
    if kind == "metadata":
        media_type = "application/json"
    return FileResponse(path=str(file_path), media_type=media_type, filename=file_path.name)


@router.get("/models/{model_id}/runtime-check")
async def runtime_check_playground_model(model_id: str, _user=Depends(role_or_internal_dep("editor"))):
    registry = _load_registry()
    entry = _get_model_entry(registry, model_id)
    try:
        result = _perform_runtime_check(entry)
        entry["runtime_status"] = {
            "state": "pass",
            "checked_at": _runtime_status_timestamp(),
            "input_dim": int(result["input_dim"]),
            "output_dim": int(result["output_dim"]),
            "message": str(result["message"]),
        }
        _save_registry(registry)
        return result
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        entry["runtime_status"] = {
            "state": "fail",
            "checked_at": _runtime_status_timestamp(),
            "message": detail,
        }
        _save_registry(registry)
        raise


@router.delete("/models/{model_id}")
async def delete_playground_model(model_id: str, _user=Depends(role_or_internal_dep("editor"))):
    registry = _load_registry()
    models = registry.get("models", [])
    entry = _get_model_entry(registry, model_id)
    remaining = [m for m in models if m.get("id") != model_id]
    registry["models"] = remaining
    if registry.get("active_model_id") == model_id:
        registry["active_model_id"] = remaining[0]["id"] if remaining else None
    _save_registry(registry)

    model_dir = (_models_root() / model_id).resolve()
    root = _models_root().resolve()
    try:
        model_dir.relative_to(root)
        if model_dir.exists() and model_dir.is_dir():
            shutil.rmtree(model_dir, ignore_errors=True)
    except ValueError:
        pass

    with MODEL_CACHE_LOCK:
        MODEL_CACHE.pop(model_id, None)
    _trigger_worker_reconcile("model delete")

    return {
        "status": "success",
        "deleted_model_id": model_id,
        "active_model_id": registry.get("active_model_id"),
        "deleted_name": entry.get("display_name"),
    }


@router.post("/predict/cv")
async def predict_playground_cv(req: PlaygroundPredictRequest, _user=Depends(role_or_internal_dep("editor"))):
    registry = _load_registry()
    model_id = req.model_id or registry.get("active_model_id")
    if not model_id:
        raise HTTPException(status_code=404, detail="No active playground model")
    model_entry = next((m for m in registry.get("models", []) if m.get("id") == model_id), None)
    if not model_entry:
        raise HTTPException(status_code=404, detail=f"Model not found: {model_id}")
    model_modality = _entry_modality(model_entry)
    if model_modality == "sensor":
        raise HTTPException(
            status_code=400,
            detail="Selected model modality is sensor, but /playground/predict/cv expects a CV model.",
        )

    expected_dim = int(model_entry.get("input_dim") or 0)
    vector = _coerce_input_vector(req.cv_values, expected_dim, "cv_values")

    if _uses_runtime_services():
        remote = _remote_predict(model_entry, vector)
        prediction = remote.get("prediction")
        if not isinstance(prediction, dict):
            raise HTTPException(status_code=502, detail="Runtime service returned invalid prediction payload")
        return {
            "status": "success",
            "model_id": model_id,
            "model_name": model_entry.get("display_name"),
            "prediction": prediction,
        }

    runtime = _load_model_runtime(model_entry)
    probs = _predict_with_runtime(runtime, vector)
    labels = [str(v) for v in (model_entry.get("metadata", {}).get("labels") or [])]
    if not labels:
        raise HTTPException(status_code=500, detail="Model metadata labels are missing")
    if len(labels) != probs.shape[0]:
        n = min(len(labels), probs.shape[0])
        labels = labels[:n]
        probs = probs[:n]

    probs = _normalize_probs(probs)

    best_idx = int(np.argmax(probs))
    best_label = labels[best_idx]
    best_confidence = float(probs[best_idx])
    probabilities = {labels[i]: float(probs[i]) for i in range(len(labels))}
    top3 = sorted(probabilities.items(), key=lambda item: item[1], reverse=True)[:3]

    return {
        "status": "success",
        "model_id": model_id,
        "model_name": model_entry.get("display_name"),
        "prediction": {
            "label": best_label,
            "confidence": best_confidence,
            "probabilities": probabilities,
            "top3": [{"label": label, "confidence": conf} for label, conf in top3],
        },
    }


@router.post("/predict/sensor")
async def predict_playground_sensor(req: PlaygroundSensorPredictRequest, _user=Depends(role_or_internal_dep("editor"))):
    registry = _load_registry()
    model_id = req.model_id or registry.get("active_model_id")
    if not model_id:
        raise HTTPException(status_code=404, detail="No active playground model")
    model_entry = next((m for m in registry.get("models", []) if m.get("id") == model_id), None)
    if not model_entry:
        raise HTTPException(status_code=404, detail=f"Model not found: {model_id}")

    model_modality = _entry_modality(model_entry)
    if model_modality == "cv":
        raise HTTPException(
            status_code=400,
            detail="Selected model modality is cv, but /playground/predict/sensor expects a sensor model.",
        )

    expected_dim = int(model_entry.get("input_dim") or 0)
    vector = _coerce_input_vector(req.sensor_values, expected_dim, "sensor_values")

    if _uses_runtime_services():
        remote = _remote_predict(model_entry, vector)
        prediction = remote.get("prediction")
        if not isinstance(prediction, dict):
            raise HTTPException(status_code=502, detail="Runtime service returned invalid prediction payload")
        return {
            "status": "success",
            "model_id": model_id,
            "model_name": model_entry.get("display_name"),
            "prediction": prediction,
        }

    runtime = _load_model_runtime(model_entry)
    probs = _predict_with_runtime(runtime, vector)
    labels = [str(v) for v in (model_entry.get("metadata", {}).get("labels") or [])]
    if not labels:
        raise HTTPException(status_code=500, detail="Model metadata labels are missing")
    if len(labels) != probs.shape[0]:
        n = min(len(labels), probs.shape[0])
        labels = labels[:n]
        probs = probs[:n]

    probs = _normalize_probs(probs)

    best_idx = int(np.argmax(probs))
    best_label = labels[best_idx]
    best_confidence = float(probs[best_idx])
    probabilities = {labels[i]: float(probs[i]) for i in range(len(labels))}
    top3 = sorted(probabilities.items(), key=lambda item: item[1], reverse=True)[:3]

    return {
        "status": "success",
        "model_id": model_id,
        "model_name": model_entry.get("display_name"),
        "prediction": {
            "label": best_label,
            "confidence": best_confidence,
            "probabilities": probabilities,
            "top3": [{"label": label, "confidence": conf} for label, conf in top3],
        },
    }
