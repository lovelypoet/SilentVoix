import os
import json
import shutil
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from api.core.settings import settings
from api.core.database import model_collection

logger = logging.getLogger("signglove.model_service")

class ModelService:
    def __init__(self):
        # Root for artifacts in V3 structure
        self.storage_root = Path(settings.BASE_DIR) / "storage" / "models"
        self.storage_root.mkdir(parents=True, exist_ok=True)

    async def register_model_from_tmp(
        self,
        name: str,
        version: str,
        model_tmp_path: Path,
        model_file_name: str,
        metadata: Dict[str, Any],
        class_tmp_path: Optional[Path] = None,
        class_file_name: Optional[str] = None
    ) -> str:
        """
        Registers a model by moving artifacts from temporary paths.
        """
        # 1. Create directory structure
        model_dir = self.storage_root / name / version
        model_dir.mkdir(parents=True, exist_ok=True)

        # 2. Move artifacts
        model_path = model_dir / model_file_name
        shutil.move(str(model_tmp_path), str(model_path))

        if class_tmp_path and class_tmp_path.exists():
            class_path = model_dir / class_file_name
            shutil.move(str(class_tmp_path), str(class_path))
        else:
            class_path = None

        # 3. Prepare metadata for DB
        model_id = str(uuid4())
        doc = {
            "id": model_id,
            "name": name,
            "version": version,
            "model_path": str(model_path),
            "class_path": str(class_path) if class_path else None,
            "metadata": metadata,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "available"
        }

        # 4. Save to MongoDB
        await model_collection.insert_one(doc)
        logger.info(f"Registered model {name} v{version} (ID: {model_id}) via move")
        
        return model_id

    async def list_models(self) -> List[Dict[str, Any]]:
        cursor = model_collection.find({}, {"_id": 0})
        return await cursor.to_list(length=1000)

    async def get_model_by_id(self, model_id: str) -> Optional[Dict[str, Any]]:
        return await model_collection.find_one({"id": model_id}, {"_id": 0})

    async def delete_model(self, model_id: str):
        model_doc = await self.get_model_by_id(model_id)
        if not model_doc:
            raise FileNotFoundError(f"Model {model_id} not found in database")

        # Remove from DB
        await model_collection.delete_one({"id": model_id})

        # Remove from storage if no other versions/models are using the directory
        # For safety, we only remove the specific version directory
        model_path = Path(model_doc["model_path"])
        version_dir = model_path.parent
        if version_dir.exists() and version_dir.is_dir():
            shutil.rmtree(version_dir)
            logger.info(f"Deleted artifacts at {version_dir}")

model_service = ModelService()
