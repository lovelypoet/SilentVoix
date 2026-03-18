from __future__ import annotations

import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import select

from api.core.database import AsyncSessionLocal
from db.models import Model
from services.model_library_service import model_library_service

logger = logging.getLogger("signglove.model_service")


def _isoformat_utc(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc).isoformat()
    return value.astimezone(timezone.utc).isoformat()


class ModelService:
    def __init__(self):
        self.storage_root = model_library_service.get_models_root()
        self.storage_root.mkdir(parents=True, exist_ok=True)

    def _model_to_entry(self, model: Model) -> Dict[str, Any]:
        config = model.config_json if isinstance(model.config_json, dict) else {}
        metadata = config.get("metadata") if isinstance(config.get("metadata"), dict) else {}
        runtime_status = config.get("runtime_status") if isinstance(config.get("runtime_status"), dict) else None

        return {
            "id": str(model.id),
            "display_name": model.name,
            "name": model.name,
            "version": model.version,
            "model_path": model.artifact_path,
            "artifact_path": model.artifact_path,
            "metadata_path": config.get("metadata_path"),
            "model_class_path": config.get("class_path"),
            "class_path": config.get("class_path"),
            "model_file_name": config.get("model_file_name") or Path(model.artifact_path).name,
            "metadata_file_name": config.get("metadata_file_name") or "metadata.json",
            "metadata": metadata,
            "input_dim": int(config.get("input_dim") or 0),
            "created_at": _isoformat_utc(model.created_at),
            "status": "available",
            "training_dataset_id": str(model.training_dataset_id) if model.training_dataset_id else None,
            "runtime_status": runtime_status,
        }

    def _row_from_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": str(entry.get("id") or ""),
            "display_name": entry.get("display_name") or entry.get("name"),
            "model_path": entry.get("model_path") or entry.get("artifact_path"),
            "metadata_path": entry.get("metadata_path"),
            "model_class_path": entry.get("model_class_path") or entry.get("class_path"),
            "model_file_name": entry.get("model_file_name"),
            "metadata_file_name": entry.get("metadata_file_name"),
            "metadata": entry.get("metadata") or {},
            "input_dim": int(entry.get("input_dim") or 0),
            "created_at": entry.get("created_at") or datetime.now(timezone.utc).isoformat(),
            "training_dataset_id": entry.get("training_dataset_id"),
            "runtime_status": entry.get("runtime_status"),
        }

    async def sync_registry_from_db(self) -> Dict[str, Any]:
        entries = await self.list_models()
        registry = model_library_service.load_registry()
        existing = [self._row_from_entry(entry) for entry in entries]
        by_id = {entry["id"]: entry for entry in existing if entry.get("id")}

        ordered: List[Dict[str, Any]] = []
        for item in registry.get("models", []):
            model_id = str(item.get("id") or "").strip()
            if model_id and model_id in by_id:
                merged = {**by_id[model_id], **({"runtime_status": item.get("runtime_status")} if item.get("runtime_status") else {})}
                ordered.append(merged)
                by_id.pop(model_id, None)

        if by_id:
            leftovers = sorted(by_id.values(), key=lambda item: str(item.get("created_at") or ""), reverse=True)
            ordered.extend(leftovers)

        active_model_id = registry.get("active_model_id")
        if active_model_id not in {entry["id"] for entry in ordered}:
            active_model_id = ordered[0]["id"] if ordered else None

        synced = {
            "models": ordered,
            "active_model_id": active_model_id,
        }
        model_library_service.save_registry(synced)
        return synced

    async def register_model_from_tmp(
        self,
        name: str,
        version: str,
        model_tmp_path: Path,
        metadata_tmp_path: Path,
        model_file_name: str,
        metadata: Dict[str, Any],
        class_tmp_path: Optional[Path] = None,
        class_file_name: Optional[str] = None,
        training_dataset_id: Optional[str] = None,
    ) -> str:
        model_id = uuid4()
        model_dir = self.storage_root / str(model_id)
        model_dir.mkdir(parents=True, exist_ok=True)

        suffix = Path(model_file_name).suffix.lower() or ".bin"
        model_path = model_dir / f"model{suffix}"
        metadata_path = model_dir / "metadata.json"

        shutil.move(str(model_tmp_path), str(model_path))
        shutil.move(str(metadata_tmp_path), str(metadata_path))

        saved_class_path: Optional[Path] = None
        if class_tmp_path and class_tmp_path.exists():
            saved_class_path = model_dir / "model.py"
            shutil.move(str(class_tmp_path), str(saved_class_path))

        input_dim = model_library_service.input_dim_from_metadata(metadata)
        export_format = str(metadata.get("export_format") or "").strip().lower()
        family = str(metadata.get("model_family") or "unknown").strip() or "unknown"
        accuracy = metadata.get("accuracy")
        f1_score = metadata.get("f1")

        config_json = {
            "metadata": metadata,
            "metadata_path": str(metadata_path),
            "metadata_file_name": "metadata.json",
            "model_file_name": model_file_name,
            "input_dim": input_dim,
            "class_path": str(saved_class_path) if saved_class_path else None,
            "class_file_name": class_file_name,
            "runtime_status": None,
        }

        try:
            async with AsyncSessionLocal() as session:
                db_model = Model(
                    id=model_id,
                    name=name,
                    family=family,
                    version=version,
                    artifact_path=str(model_path),
                    export_format=export_format,
                    accuracy=float(accuracy) if isinstance(accuracy, (int, float)) else None,
                    f1_score=float(f1_score) if isinstance(f1_score, (int, float)) else None,
                    config_json=config_json,
                    training_dataset_id=UUID(training_dataset_id) if training_dataset_id else None,
                    created_at=datetime.now(timezone.utc).replace(tzinfo=None),
                )
                session.add(db_model)
                await session.commit()
        except Exception:
            shutil.rmtree(model_dir, ignore_errors=True)
            raise

        logger.info("Registered model %s v%s (ID: %s) in PostgreSQL", name, version, model_id)
        return str(model_id)

    async def list_models(self) -> List[Dict[str, Any]]:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Model).order_by(Model.created_at.desc()))
            rows = result.scalars().all()
        return [self._model_to_entry(row) for row in rows]

    async def get_model_by_id(self, model_id: str) -> Optional[Dict[str, Any]]:
        try:
            model_uuid = UUID(model_id)
        except (TypeError, ValueError):
            return None
        async with AsyncSessionLocal() as session:
            row = await session.get(Model, model_uuid)
        return self._model_to_entry(row) if row else None

    async def update_model_runtime_status(self, model_id: str, runtime_status: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        try:
            model_uuid = UUID(model_id)
        except (TypeError, ValueError):
            return None
        async with AsyncSessionLocal() as session:
            row = await session.get(Model, model_uuid)
            if not row:
                return None
            config = row.config_json if isinstance(row.config_json, dict) else {}
            config["runtime_status"] = runtime_status
            row.config_json = config
            await session.commit()
            await session.refresh(row)
        return self._model_to_entry(row)

    async def delete_model(self, model_id: str):
        try:
            model_uuid = UUID(model_id)
        except (TypeError, ValueError) as exc:
            raise FileNotFoundError(f"Model {model_id} not found in database") from exc
        async with AsyncSessionLocal() as session:
            row = await session.get(Model, model_uuid)
            if not row:
                raise FileNotFoundError(f"Model {model_id} not found in database")
            artifact_path = Path(row.artifact_path)
            await session.delete(row)
            await session.commit()

        model_dir = artifact_path.parent
        if model_dir.exists() and model_dir.is_dir():
            shutil.rmtree(model_dir, ignore_errors=True)
            logger.info("Deleted artifacts at %s", model_dir)


model_service = ModelService()
