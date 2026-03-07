from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

import numpy as np
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Query, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel

from services.playground_service import playground_service
from routes.auth_routes import role_or_internal_dep

router = APIRouter(prefix="/playground", tags=["Realtime AI Playground"])
logger = logging.getLogger("signglove.playground")


class PlaygroundPredictRequest(BaseModel):
    model_config = {"protected_namespaces": ()}
    cv_values: List[float]
    model_id: Optional[str] = None


class PlaygroundSensorPredictRequest(BaseModel):
    model_config = {"protected_namespaces": ()}
    sensor_values: List[float]
    model_id: Optional[str] = None


class PlaygroundModelReorderRequest(BaseModel):
    model_ids: List[str]


def _runtime_status_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _compute_runtime_status(entry: Dict[str, Any]) -> Dict[str, Any]:
    try:
        result = playground_service.perform_runtime_check(entry)
        return {
            "state": "pass",
            "checked_at": _runtime_status_timestamp(),
            "input_dim": int(result["input_dim"]),
            "output_dim": int(result["output_dim"]),
            "message": str(result["message"]),
        }
    except Exception as exc:
        detail = str(exc)
        return {
            "state": "fail",
            "checked_at": _runtime_status_timestamp(),
            "message": detail,
        }


@router.post("/models/upload")
async def upload_playground_model(
    artifact_file: UploadFile = File(..., alias="model_file"),
    metadata_file: UploadFile = File(...),
    class_file: Optional[UploadFile] = File(None, alias="model_class_file"),
    is_state_dict: str = Form("false"),
    _user=Depends(role_or_internal_dep("editor")),
):
    model_name = Path(artifact_file.filename or "").name
    metadata_name = Path(metadata_file.filename or "").name
    if not model_name:
        raise HTTPException(status_code=400, detail="model_file is required")
    if not metadata_name.lower().endswith(".json"):
        raise HTTPException(status_code=400, detail="metadata_file must be a .json file")

    suffix = Path(model_name).suffix.lower()
    model_bytes = await artifact_file.read()
    metadata_bytes = await metadata_file.read()
    if not model_bytes:
        raise HTTPException(status_code=400, detail="Uploaded model file is empty")
    if not metadata_bytes:
        raise HTTPException(status_code=400, detail="Uploaded metadata file is empty")

    try:
        metadata = json.loads(metadata_bytes.decode("utf-8"))
        if not isinstance(metadata, dict):
            raise ValueError("Metadata must be a JSON object")
        playground_service.validate_metadata(metadata, suffix)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    try:
        input_dim = playground_service.input_dim_from_metadata(metadata)
        modality = playground_service.resolve_model_modality(metadata, input_dim)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if modality:
        metadata["modality"] = modality
        metadata.setdefault("input_spec", {})
        if isinstance(metadata["input_spec"], dict):
            metadata["input_spec"]["modality"] = modality

    is_state_dict_bool = str(is_state_dict).lower() == "true"
    metadata["is_state_dict"] = is_state_dict_bool
    metadata["has_model_class"] = class_file is not None

    model_id = str(uuid4())
    model_dir = playground_service.get_models_root() / model_id
    model_dir.mkdir(parents=True, exist_ok=True)
    saved_model_path = model_dir / f"model{suffix}"
    saved_metadata_path = model_dir / "metadata.json"
    saved_model_path.write_bytes(model_bytes)
    saved_metadata_path.write_bytes(metadata_bytes)
    
    saved_model_class_path = None
    if class_file:
        model_class_bytes = await class_file.read()
        saved_model_class_path = model_dir / "model.py"
        saved_model_class_path.write_bytes(model_class_bytes)

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
    if saved_model_class_path:
        entry["model_class_path"] = str(saved_model_class_path)

    entry["runtime_status"] = _compute_runtime_status(entry)

    registry = playground_service.load_registry()
    registry["models"] = [*registry.get("models", []), entry]
    registry["active_model_id"] = model_id
    playground_service.save_registry(registry)
    playground_service.clear_cache(model_id)
    playground_service.trigger_worker_reconcile("model upload")

    return {
        "status": "success",
        "model": entry,
        "active_model_id": model_id,
        "message": "Model uploaded and set as active",
    }


@router.get("/models")
async def list_playground_models(_user=Depends(role_or_internal_dep("editor"))):
    registry = playground_service.load_registry()
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

    registry = playground_service.load_registry()
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
    reordered = [by_id[model_id] for model_id in deduped_ids]
    registry["models"] = [*reordered, *remaining]
    playground_service.save_registry(registry)
    
    return {
        "status": "success",
        "models": registry.get("models", []),
        "active_model_id": registry.get("active_model_id"),
    }


@router.get("/models/active")
async def get_active_playground_model(_user=Depends(role_or_internal_dep("editor"))):
    registry = playground_service.load_registry()
    active_id = registry.get("active_model_id")
    active = next((m for m in registry.get("models", []) if m.get("id") == active_id), None)
    return {
        "status": "success",
        "active_model_id": active_id,
        "model": active,
    }


@router.post("/models/{model_id}/activate")
async def activate_playground_model(model_id: str, _user=Depends(role_or_internal_dep("editor"))):
    registry = playground_service.load_registry()
    try:
        target = playground_service.get_model_entry(registry, model_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
        
    registry["active_model_id"] = model_id
    target["runtime_status"] = _compute_runtime_status(target)
    playground_service.save_registry(registry)
    playground_service.trigger_worker_reconcile("model activate")
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
    registry = playground_service.load_registry()
    try:
        entry = playground_service.get_model_entry(registry, model_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
        
    field_name = "model_path" if kind == "model" else "metadata_path"
    raw_path = entry.get(field_name)
    if not raw_path:
        raise HTTPException(status_code=404, detail=f"Artifact missing: {field_name}")
    
    file_path = Path(str(raw_path)).resolve()
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"Artifact file not found: {file_path.name}")
    
    media_type = "application/octet-stream"
    if kind == "metadata":
        media_type = "application/json"
    return FileResponse(path=str(file_path), media_type=media_type, filename=file_path.name)


@router.get("/models/{model_id}/runtime-check")
async def runtime_check_playground_model(model_id: str, _user=Depends(role_or_internal_dep("editor"))):
    registry = playground_service.load_registry()
    try:
        entry = playground_service.get_model_entry(registry, model_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
        
    try:
        result = playground_service.perform_runtime_check(entry)
        entry["runtime_status"] = {
            "state": "pass",
            "checked_at": _runtime_status_timestamp(),
            "input_dim": int(result["input_dim"]),
            "output_dim": int(result["output_dim"]),
            "message": str(result["message"]),
        }
        playground_service.save_registry(registry)
        return result
    except Exception as exc:
        detail = str(exc)
        entry["runtime_status"] = {
            "state": "fail",
            "checked_at": _runtime_status_timestamp(),
            "message": detail,
        }
        playground_service.save_registry(registry)
        raise HTTPException(status_code=400, detail=detail)


@router.delete("/models/{model_id}")
async def delete_playground_model(model_id: str, _user=Depends(role_or_internal_dep("editor"))):
    registry = playground_service.load_registry()
    models = registry.get("models", [])
    try:
        entry = playground_service.get_model_entry(registry, model_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
        
    remaining = [m for m in models if m.get("id") != model_id]
    registry["models"] = remaining
    if registry.get("active_model_id") == model_id:
        registry["active_model_id"] = remaining[0]["id"] if remaining else None
    playground_service.save_registry(registry)

    model_dir = (playground_service.get_models_root() / model_id).resolve()
    if model_dir.exists() and model_dir.is_dir():
        import shutil
        shutil.rmtree(model_dir, ignore_errors=True)

    playground_service.clear_cache(model_id)
    playground_service.trigger_worker_reconcile("model delete")

    return {
        "status": "success",
        "deleted_model_id": model_id,
        "active_model_id": registry.get("active_model_id"),
        "deleted_name": entry.get("display_name"),
    }


@router.post("/predict/cv")
async def predict_playground_cv(req: PlaygroundPredictRequest, _user=Depends(role_or_internal_dep("editor"))):
    registry = playground_service.load_registry()
    model_id = req.model_id or registry.get("active_model_id")
    if not model_id:
        raise HTTPException(status_code=404, detail="No active playground model")
        
    try:
        model_entry = playground_service.get_model_entry(registry, model_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
        
    model_modality = playground_service.get_entry_modality(model_entry)
    if model_modality == "sensor":
        raise HTTPException(
            status_code=400,
            detail="Selected model modality is sensor, but /playground/predict/cv expects a CV model.",
        )

    expected_dim = int(model_entry.get("input_dim") or 0)
    try:
        vector = playground_service.coerce_input_vector(req.cv_values, expected_dim, "cv_values")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    from core.settings import settings
    if bool(settings.USE_RUNTIME_SERVICES):
        try:
            remote = playground_service.remote_predict(model_entry, vector)
            prediction = remote.get("prediction")
            if not isinstance(prediction, dict):
                raise HTTPException(status_code=502, detail="Runtime service returned invalid prediction payload")
            return {
                "status": "success",
                "model_id": model_id,
                "model_name": model_entry.get("display_name"),
                "prediction": prediction,
            }
        except Exception as exc:
            raise HTTPException(status_code=502, detail=str(exc))

    try:
        runtime = playground_service.load_model_runtime(model_entry)
        probs = playground_service.predict_with_runtime(runtime, vector)
        labels = [str(v) for v in (model_entry.get("metadata", {}).get("labels") or [])]
        if not labels:
            raise HTTPException(status_code=500, detail="Model metadata labels are missing")
        
        probs = np.asarray(probs, dtype=np.float32).reshape(-1)
        if len(labels) != probs.shape[0]:
            n = min(len(labels), probs.shape[0])
            labels = labels[:n]
            probs = probs[:n]

        probs = playground_service.normalize_probs(probs)

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
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/predict/sensor")
async def predict_playground_sensor(req: PlaygroundSensorPredictRequest, _user=Depends(role_or_internal_dep("editor"))):
    registry = playground_service.load_registry()
    model_id = req.model_id or registry.get("active_model_id")
    if not model_id:
        raise HTTPException(status_code=404, detail="No active playground model")
        
    try:
        model_entry = playground_service.get_model_entry(registry, model_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    model_modality = playground_service.get_entry_modality(model_entry)
    if model_modality == "cv":
        raise HTTPException(
            status_code=400,
            detail="Selected model modality is cv, but /playground/predict/sensor expects a sensor model.",
        )

    expected_dim = int(model_entry.get("input_dim") or 0)
    try:
        vector = playground_service.coerce_input_vector(req.sensor_values, expected_dim, "sensor_values")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    from core.settings import settings
    if bool(settings.USE_RUNTIME_SERVICES):
        try:
            remote = playground_service.remote_predict(model_entry, vector)
            prediction = remote.get("prediction")
            if not isinstance(prediction, dict):
                raise HTTPException(status_code=502, detail="Runtime service returned invalid prediction payload")
            return {
                "status": "success",
                "model_id": model_id,
                "model_name": model_entry.get("display_name"),
                "prediction": prediction,
            }
        except Exception as exc:
            raise HTTPException(status_code=502, detail=str(exc))

    try:
        runtime = playground_service.load_model_runtime(model_entry)
        probs = playground_service.predict_with_runtime(runtime, vector)
        labels = [str(v) for v in (model_entry.get("metadata", {}).get("labels") or [])]
        if not labels:
            raise HTTPException(status_code=500, detail="Model metadata labels are missing")
        
        probs = np.asarray(probs, dtype=np.float32).reshape(-1)
        if len(labels) != probs.shape[0]:
            n = min(len(labels), probs.shape[0])
            labels = labels[:n]
            probs = probs[:n]

        probs = playground_service.normalize_probs(probs)

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
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
