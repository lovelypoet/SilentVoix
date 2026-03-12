from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

import numpy as np
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Query, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel

from services.model_library_service import model_library_service
from services.models.model_service import model_service
from api.routes.auth_routes import role_or_internal_dep
from api.core.settings import settings

router = APIRouter(prefix="/model-library", tags=["Model Library"])
logger = logging.getLogger("signglove.model_library")

class PlaygroundPredictRequest(BaseModel):
    model_config = {"protected_namespaces": ()}
    cv_values: Optional[List[float]] = None
    sequence: Optional[List[List[float]]] = None
    model_id: Optional[str] = None

class PlaygroundSensorPredictRequest(BaseModel):
    model_config = {"protected_namespaces": ()}
    sensor_values: List[float]
    model_id: Optional[str] = None

@router.post("/models/upload")
async def upload_playground_model(
    artifact_file: UploadFile = File(..., alias="model_file"),
    metadata_file: UploadFile = File(...),
    class_file: Optional[UploadFile] = File(None, alias="model_class_file"),
    version: str = Form("v1"),
    _user=Depends(role_or_internal_dep("editor")),
):
    model_filename = Path(artifact_file.filename or "").name
    metadata_filename = Path(metadata_file.filename or "").name
    
    if not model_filename:
        raise HTTPException(status_code=400, detail="model_file is required")
    
    model_bytes = await artifact_file.read()
    metadata_bytes = await metadata_file.read()
    class_bytes = await class_file.read() if class_file else None
    
    try:
        metadata = json.loads(metadata_bytes.decode("utf-8"))
        model_name = metadata.get("model_name", Path(model_filename).stem)
        
        # Register in V3 structured storage & DB
        model_id = await model_service.register_model(
            name=model_name,
            version=version,
            model_file_content=model_bytes,
            model_file_name=model_filename,
            metadata=metadata,
            class_file_content=class_bytes,
            class_file_name=class_file.filename if class_file else None
        )
        
        # Backward Compatibility: Update legacy registry.json for now
        # (This ensures existing UI and ML runtimes don't break immediately)
        registry = model_library_service.load_registry()
        entry = {
            "id": model_id,
            "display_name": model_name,
            "model_path": str(Path(settings.BASE_DIR) / "storage/models" / model_name / version / model_filename),
            "metadata": metadata,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        registry["models"].append(entry)
        registry["active_model_id"] = model_id
        model_library_service.save_registry(registry)
        
        return {
            "status": "success",
            "model_id": model_id,
            "message": f"Model registered successfully in V3 storage (v{version})"
        }
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/models")
async def list_playground_models(_user=Depends(role_or_internal_dep("editor"))):
    models = await model_service.list_models()
    return {"status": "success", "models": models}

@router.get("/models/{model_id}")
async def get_model_details(model_id: str, _user=Depends(role_or_internal_dep("editor"))):
    model = await model_service.get_model_by_id(model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return {"status": "success", "model": model}

@router.delete("/models/{model_id}")
async def delete_model(model_id: str, _user=Depends(role_or_internal_dep("editor"))):
    try:
        await model_service.delete_model(model_id)
        return {"status": "success", "message": f"Model {model_id} deleted"}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
