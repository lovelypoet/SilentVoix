from __future__ import annotations

import json
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

import numpy as np
import tensorflow as tf
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from core.settings import settings
from routes.auth_routes import role_or_internal_dep

router = APIRouter(prefix="/playground", tags=["Realtime AI Playground"])

ALLOWED_MODEL_EXTENSIONS = {".tflite", ".keras", ".h5"}
ALLOWED_EXPORT_FORMATS = {"tflite", "tensorflow-lite", "keras", "h5"}
MODEL_CACHE_LOCK = threading.Lock()
MODEL_CACHE: Dict[str, Dict[str, Any]] = {}


class PlaygroundPredictRequest(BaseModel):
    cv_values: List[float]
    model_id: Optional[str] = None


def _models_root() -> Path:
    root = Path(settings.UPLOAD_DIR) / "playground_models"
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
    if export_format not in ALLOWED_EXPORT_FORMATS:
        raise HTTPException(status_code=400, detail=f"Unsupported export_format: {export_format}")

    # Validate extension and format consistency.
    suffix = model_suffix.lower()
    if suffix not in ALLOWED_MODEL_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported model file extension: {suffix}")
    if suffix == ".tflite" and export_format not in {"tflite", "tensorflow-lite"}:
        raise HTTPException(status_code=400, detail="Model extension .tflite requires export_format=tflite|tensorflow-lite")
    if suffix in {".keras", ".h5"} and export_format not in {"keras", "h5"}:
        raise HTTPException(status_code=400, detail="Model extension .keras/.h5 requires export_format=keras|h5")


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


def _normalize_model_output(output: np.ndarray) -> np.ndarray:
    if output.ndim == 0:
        return np.array([float(output)], dtype=np.float32)
    if output.ndim == 1:
        return output.astype(np.float32)
    if output.ndim >= 2:
        first = output[0]
        return np.asarray(first, dtype=np.float32).reshape(-1)
    return output.astype(np.float32).reshape(-1)


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
    runtime: Dict[str, Any] = {"mtime": model_mtime, "export_format": export_format}
    if export_format in {"tflite", "tensorflow-lite"}:
        interpreter = tf.lite.Interpreter(model_path=str(model_path))
        interpreter.allocate_tensors()
        runtime["interpreter"] = interpreter
        runtime["input_details"] = interpreter.get_input_details()
        runtime["output_details"] = interpreter.get_output_details()
    elif export_format in {"keras", "h5"}:
        runtime["model"] = tf.keras.models.load_model(str(model_path), compile=False)
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported export_format at runtime: {export_format}")

    with MODEL_CACHE_LOCK:
        MODEL_CACHE[model_id] = runtime
    return runtime


def _predict_with_runtime(runtime: Dict[str, Any], cv_values: np.ndarray) -> np.ndarray:
    export_format = runtime["export_format"]
    if export_format in {"tflite", "tensorflow-lite"}:
        interpreter = runtime["interpreter"]
        input_details = runtime["input_details"][0]
        output_details = runtime["output_details"][0]

        input_dtype = input_details.get("dtype", np.float32)
        input_shape = input_details.get("shape", np.array([1, cv_values.shape[0]]))
        if len(input_shape) == 2:
            feed = cv_values.reshape(1, -1).astype(input_dtype)
        else:
            # Generic fallback: preserve batch axis, flatten to model width if possible.
            feed = cv_values.reshape(1, -1).astype(input_dtype)
        interpreter.set_tensor(input_details["index"], feed)
        interpreter.invoke()
        output = interpreter.get_tensor(output_details["index"])
        return _normalize_model_output(np.asarray(output))

    model = runtime["model"]
    raw = model.predict(cv_values.reshape(1, -1), verbose=0)
    return _normalize_model_output(np.asarray(raw))


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

    registry = _load_registry()
    registry["models"] = [*registry.get("models", []), entry]
    registry["active_model_id"] = model_id
    _save_registry(registry)
    with MODEL_CACHE_LOCK:
        MODEL_CACHE.pop(model_id, None)

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
    _save_registry(registry)
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

    expected_dim = int(model_entry.get("input_dim") or 0)
    vector = np.asarray(req.cv_values, dtype=np.float32).reshape(-1)
    if expected_dim <= 0:
        raise HTTPException(status_code=500, detail="Invalid model input dimension")
    if vector.shape[0] != expected_dim:
        raise HTTPException(
            status_code=400,
            detail=f"cv_values length mismatch: expected {expected_dim}, got {vector.shape[0]}",
        )

    runtime = _load_model_runtime(model_entry)
    probs = _predict_with_runtime(runtime, vector)
    labels = [str(v) for v in (model_entry.get("metadata", {}).get("labels") or [])]
    if not labels:
        raise HTTPException(status_code=500, detail="Model metadata labels are missing")
    if len(labels) != probs.shape[0]:
        n = min(len(labels), probs.shape[0])
        labels = labels[:n]
        probs = probs[:n]

    # Normalize probabilities if needed.
    probs = np.asarray(probs, dtype=np.float32)
    if probs.size == 0:
        raise HTTPException(status_code=500, detail="Model returned empty prediction")
    if np.any(probs < 0) or probs.sum() <= 0:
        exp = np.exp(probs - np.max(probs))
        probs = exp / np.sum(exp)
    else:
        total = float(np.sum(probs))
        probs = probs / total

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
