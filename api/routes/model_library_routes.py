from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from api.core.settings import settings
from api.routes.auth_routes import role_or_internal_dep
from api.utils.upload_utils import handle_streaming_upload
from services.model_library_service import model_library_service
from services.models.model_service import model_service

router = APIRouter(prefix="/model-library", tags=["Model Library"])
logger = logging.getLogger("signglove.model_library")


class PlaygroundModelReorderRequest(BaseModel):
    model_config = {"protected_namespaces": ()}
    model_ids: List[str]


class PlaygroundPredictRequest(BaseModel):
    model_config = {"protected_namespaces": ()}
    cv_values: Optional[List[float]] = None
    sequence: Optional[List[List[float]]] = None
    model_id: Optional[str] = None


class PlaygroundSensorPredictRequest(BaseModel):
    model_config = {"protected_namespaces": ()}
    sensor_values: List[float]
    model_id: Optional[str] = None


def _runtime_status_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _synced_registry() -> Dict[str, Any]:
    return await model_service.sync_registry_from_db()


def _compute_runtime_status(entry: Dict[str, Any]) -> Dict[str, Any]:
    try:
        result = model_library_service.perform_runtime_check(entry)
        return {
            "state": "pass",
            "checked_at": _runtime_status_timestamp(),
            "input_dim": int(result["input_dim"]),
            "output_dim": int(result["output_dim"]),
            "message": str(result["message"]),
        }
    except Exception as exc:
        return {
            "state": "fail",
            "checked_at": _runtime_status_timestamp(),
            "message": str(exc),
        }


async def _resolve_model_entry(model_id: Optional[str]) -> Dict[str, Any]:
    if model_id:
        model = await model_service.get_model_by_id(model_id)
        if not model:
            raise HTTPException(status_code=404, detail="Model not found")
        return model

    registry = await _synced_registry()
    active_id = registry.get("active_model_id")
    if not active_id:
        raise HTTPException(status_code=404, detail="No active playground model")

    model = await model_service.get_model_by_id(str(active_id))
    if not model:
        raise HTTPException(status_code=404, detail="Active model not found")
    return model


@router.post("/models/upload")
async def upload_playground_model(
    artifact_file: UploadFile = File(..., alias="model_file"),
    metadata_file: UploadFile = File(...),
    class_file: Optional[UploadFile] = File(None, alias="model_class_file"),
    version: str = Form("v1"),
    is_state_dict: str = Form("false"),
    training_dataset_id: Optional[str] = Form(None),
    _user=Depends(role_or_internal_dep("editor")),
):
    model_filename = Path(artifact_file.filename or "").name
    metadata_filename = Path(metadata_file.filename or "").name
    if not model_filename:
        raise HTTPException(status_code=400, detail="model_file is required")
    if not metadata_filename.lower().endswith(".json"):
        raise HTTPException(status_code=400, detail="metadata_file must be a .json file")

    tmp_model = None
    tmp_meta = None
    tmp_class = None

    try:
        tmp_model = await handle_streaming_upload(
            artifact_file,
            max_size=settings.MAX_MODEL_SIZE,
            allowed_extensions=[".h5", ".tflite", ".pt", ".bin", ".onnx"],
        )
        tmp_meta = await handle_streaming_upload(
            metadata_file,
            max_size=10 * 1024 * 1024,
            allowed_extensions=[".json"],
        )
        if class_file:
            tmp_class = await handle_streaming_upload(
                class_file,
                max_size=10 * 1024 * 1024,
                allowed_extensions=[".py", ".txt"],
            )

        metadata = json.loads(tmp_meta.read_text(encoding="utf-8"))
        if not isinstance(metadata, dict):
            raise HTTPException(status_code=400, detail="Metadata must be a JSON object")

        suffix = Path(model_filename).suffix.lower()
        model_library_service.validate_metadata(metadata, suffix)
        input_dim = model_library_service.input_dim_from_metadata(metadata)
        modality = model_library_service.resolve_model_modality(metadata, input_dim)
        if modality:
            metadata["modality"] = modality
            metadata.setdefault("input_spec", {})
            if isinstance(metadata["input_spec"], dict):
                metadata["input_spec"]["modality"] = modality

        metadata["is_state_dict"] = str(is_state_dict).lower() == "true"
        metadata["has_model_class"] = class_file is not None
        model_name = str(metadata.get("model_name") or Path(model_filename).stem)
        effective_version = str(version or metadata.get("version") or "v1")

        model_id = await model_service.register_model_from_tmp(
            name=model_name,
            version=effective_version,
            model_tmp_path=tmp_model,
            metadata_tmp_path=tmp_meta,
            model_file_name=model_filename,
            metadata=metadata,
            class_tmp_path=tmp_class,
            class_file_name=class_file.filename if class_file else None,
            training_dataset_id=training_dataset_id,
        )
        tmp_model = None
        tmp_meta = None
        tmp_class = None

        entry = await model_service.get_model_by_id(model_id)
        if not entry:
            raise HTTPException(status_code=500, detail="Model was created but could not be reloaded")

        runtime_status = _compute_runtime_status(entry)
        entry = await model_service.update_model_runtime_status(model_id, runtime_status) or entry

        registry = await _synced_registry()
        registry["active_model_id"] = model_id
        model_library_service.save_registry(registry)
        model_library_service.clear_cache(model_id)
        model_library_service.trigger_worker_reconcile("model upload")

        return {
            "status": "success",
            "model": entry,
            "model_id": model_id,
            "active_model_id": model_id,
            "message": "Model uploaded and set as active",
        }
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Upload failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
    finally:
        for path in (tmp_model, tmp_meta, tmp_class):
            if path and path.exists():
                path.unlink()


@router.get("/models")
async def list_playground_models(_user=Depends(role_or_internal_dep("editor"))):
    registry = await _synced_registry()
    return {
        "status": "success",
        "models": registry.get("models", []),
        "active_model_id": registry.get("active_model_id"),
    }


@router.post("/models/reorder")
async def reorder_playground_models(
    req: PlaygroundModelReorderRequest,
    _user=Depends(role_or_internal_dep("editor")),
):
    ordered_ids = [str(model_id).strip() for model_id in req.model_ids if str(model_id).strip()]
    if not ordered_ids:
        raise HTTPException(status_code=400, detail="model_ids must contain at least one model id")

    registry = await _synced_registry()
    models = [entry for entry in registry.get("models", []) if isinstance(entry, dict)]
    by_id = {str(entry.get("id") or ""): entry for entry in models}

    missing = [model_id for model_id in ordered_ids if model_id not in by_id]
    if missing:
        raise HTTPException(status_code=404, detail=f"Model not found: {missing[0]}")

    seen: set[str] = set()
    deduped_ids: List[str] = []
    for model_id in ordered_ids:
        if model_id in seen:
            continue
        seen.add(model_id)
        deduped_ids.append(model_id)

    remaining = [entry for entry in models if str(entry.get("id") or "") not in seen]
    registry["models"] = [*[by_id[model_id] for model_id in deduped_ids], *remaining]
    model_library_service.save_registry(registry)

    return {
        "status": "success",
        "models": registry.get("models", []),
        "active_model_id": registry.get("active_model_id"),
    }


@router.get("/models/active")
async def get_active_playground_model(_user=Depends(role_or_internal_dep("editor"))):
    registry = await _synced_registry()
    active_id = registry.get("active_model_id")
    active = next((entry for entry in registry.get("models", []) if entry.get("id") == active_id), None)
    return {
        "status": "success",
        "active_model_id": active_id,
        "model": active,
    }


@router.post("/models/{model_id}/activate")
async def activate_playground_model(model_id: str, _user=Depends(role_or_internal_dep("editor"))):
    registry = await _synced_registry()
    try:
        target = model_library_service.get_model_entry(registry, model_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    runtime_status = _compute_runtime_status(target)
    target = await model_service.update_model_runtime_status(model_id, runtime_status) or target
    registry = await _synced_registry()
    registry["active_model_id"] = model_id
    model_library_service.save_registry(registry)
    model_library_service.trigger_worker_reconcile("model activate")
    return {
        "status": "success",
        "active_model_id": model_id,
        "model": target,
    }


@router.get("/models/{model_id}")
async def get_model_details(model_id: str, _user=Depends(role_or_internal_dep("editor"))):
    model = await model_service.get_model_by_id(model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return {"status": "success", "model": model}


@router.get("/models/{model_id}/download")
async def download_playground_model_artifact(
    model_id: str,
    kind: str = Query("model", pattern="^(model|metadata)$"),
    _user=Depends(role_or_internal_dep("editor")),
):
    model = await model_service.get_model_by_id(model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    field_name = "model_path" if kind == "model" else "metadata_path"
    raw_path = model.get(field_name)
    if not raw_path:
        raise HTTPException(status_code=404, detail=f"Artifact missing: {field_name}")

    file_path = Path(str(raw_path)).resolve()
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"Artifact file not found: {file_path.name}")

    media_type = "application/octet-stream" if kind == "model" else "application/json"
    return FileResponse(path=str(file_path), media_type=media_type, filename=file_path.name)


@router.get("/models/{model_id}/runtime-check")
async def runtime_check_playground_model(model_id: str, _user=Depends(role_or_internal_dep("editor"))):
    model = await model_service.get_model_by_id(model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")

    try:
        result = model_library_service.perform_runtime_check(model)
        runtime_status = {
            "state": "pass",
            "checked_at": _runtime_status_timestamp(),
            "input_dim": int(result["input_dim"]),
            "output_dim": int(result["output_dim"]),
            "message": str(result["message"]),
        }
        await model_service.update_model_runtime_status(model_id, runtime_status)
        await _synced_registry()
        return result
    except Exception as exc:
        runtime_status = {
            "state": "fail",
            "checked_at": _runtime_status_timestamp(),
            "message": str(exc),
        }
        await model_service.update_model_runtime_status(model_id, runtime_status)
        await _synced_registry()
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/predict/cv")
async def predict_playground_cv(req: PlaygroundPredictRequest, _user=Depends(role_or_internal_dep("editor"))):
    model_entry = await _resolve_model_entry(req.model_id)

    model_modality = model_library_service.get_entry_modality(model_entry)
    if model_modality == "sensor":
        raise HTTPException(
            status_code=400,
            detail="Selected model modality is sensor, but /model-library/predict/cv expects a CV model.",
        )

    expected_dim = int(model_entry.get("input_dim") or 0)
    try:
        if req.sequence is not None:
            vector = model_library_service.preprocess_cv_sequence(req.sequence, model_entry.get("metadata", {}))
            if vector.shape[0] != expected_dim:
                raise ValueError(f"Preprocessed sequence length mismatch: expected {expected_dim}, got {vector.shape[0]}")
        elif req.cv_values is not None:
            vector = model_library_service.coerce_input_vector(req.cv_values, expected_dim, "cv_values")
        else:
            raise HTTPException(status_code=400, detail="Either 'cv_values' or 'sequence' must be provided.")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if bool(settings.USE_RUNTIME_SERVICES):
        try:
            remote = model_library_service.remote_predict(model_entry, vector)
            prediction = remote.get("prediction")
            if not isinstance(prediction, dict):
                raise HTTPException(status_code=502, detail="Runtime service returned invalid prediction payload")
            return {
                "status": "success",
                "model_id": model_entry.get("id"),
                "model_name": model_entry.get("display_name"),
                "prediction": prediction,
            }
        except Exception as exc:
            raise HTTPException(status_code=502, detail=str(exc))

    try:
        runtime = model_library_service.load_model_runtime(model_entry)
        probs = model_library_service.predict_with_runtime(runtime, vector)
        labels = [str(v) for v in (model_entry.get("metadata", {}).get("labels") or [])]
        if not labels:
            raise HTTPException(status_code=500, detail="Model metadata labels are missing")

        probs = np.asarray(probs, dtype=np.float32).reshape(-1)
        if len(labels) != probs.shape[0]:
            n = min(len(labels), probs.shape[0])
            labels = labels[:n]
            probs = probs[:n]

        probs = model_library_service.normalize_probs(probs)
        best_idx = int(np.argmax(probs))
        best_label = labels[best_idx]
        best_confidence = float(probs[best_idx])
        probabilities = {labels[i]: float(probs[i]) for i in range(len(labels))}
        top3 = sorted(probabilities.items(), key=lambda item: item[1], reverse=True)[:3]

        return {
            "status": "success",
            "model_id": model_entry.get("id"),
            "model_name": model_entry.get("display_name"),
            "prediction": {
                "label": best_label,
                "confidence": best_confidence,
                "probabilities": probabilities,
                "top3": [{"label": label, "confidence": conf} for label, conf in top3],
            },
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/predict/sensor")
async def predict_playground_sensor(req: PlaygroundSensorPredictRequest, _user=Depends(role_or_internal_dep("editor"))):
    model_entry = await _resolve_model_entry(req.model_id)

    model_modality = model_library_service.get_entry_modality(model_entry)
    if model_modality == "cv":
        raise HTTPException(
            status_code=400,
            detail="Selected model modality is cv, but /model-library/predict/sensor expects a sensor model.",
        )

    expected_dim = int(model_entry.get("input_dim") or 0)
    try:
        vector = model_library_service.coerce_input_vector(req.sensor_values, expected_dim, "sensor_values")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if bool(settings.USE_RUNTIME_SERVICES):
        try:
            remote = model_library_service.remote_predict(model_entry, vector)
            prediction = remote.get("prediction")
            if not isinstance(prediction, dict):
                raise HTTPException(status_code=502, detail="Runtime service returned invalid prediction payload")
            return {
                "status": "success",
                "model_id": model_entry.get("id"),
                "model_name": model_entry.get("display_name"),
                "prediction": prediction,
            }
        except Exception as exc:
            raise HTTPException(status_code=502, detail=str(exc))

    try:
        runtime = model_library_service.load_model_runtime(model_entry)
        probs = model_library_service.predict_with_runtime(runtime, vector)
        labels = [str(v) for v in (model_entry.get("metadata", {}).get("labels") or [])]
        if not labels:
            raise HTTPException(status_code=500, detail="Model metadata labels are missing")

        probs = np.asarray(probs, dtype=np.float32).reshape(-1)
        if len(labels) != probs.shape[0]:
            n = min(len(labels), probs.shape[0])
            labels = labels[:n]
            probs = probs[:n]

        probs = model_library_service.normalize_probs(probs)
        best_idx = int(np.argmax(probs))
        best_label = labels[best_idx]
        best_confidence = float(probs[best_idx])
        probabilities = {labels[i]: float(probs[i]) for i in range(len(labels))}
        top3 = sorted(probabilities.items(), key=lambda item: item[1], reverse=True)[:3]

        return {
            "status": "success",
            "model_id": model_entry.get("id"),
            "model_name": model_entry.get("display_name"),
            "prediction": {
                "label": best_label,
                "confidence": best_confidence,
                "probabilities": probabilities,
                "top3": [{"label": label, "confidence": conf} for label, conf in top3],
            },
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/models/{model_id}")
async def delete_model(model_id: str, _user=Depends(role_or_internal_dep("editor"))):
    try:
        await model_service.delete_model(model_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    registry = await _synced_registry()
    model_library_service.clear_cache(model_id)
    model_library_service.trigger_worker_reconcile("model delete")
    return {
        "status": "success",
        "deleted_model_id": model_id,
        "active_model_id": registry.get("active_model_id"),
    }
