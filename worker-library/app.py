from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
logger = logging.getLogger("worker-library")

MODEL_LIBRARY_DIR = Path(os.getenv("MODEL_LIBRARY_DIR", "/app/AI/model_library")).resolve()
REGISTRY_PATH = MODEL_LIBRARY_DIR / "registry.json"
RECONCILE_INTERVAL_SEC = int(os.getenv("WORKER_RECONCILE_INTERVAL_SEC", "300"))
RECONCILE_PRUNE_MISSING = os.getenv("WORKER_RECONCILE_PRUNE_MISSING", "false").lower() == "true"
RECONCILE_APPLY_ON_STARTUP = os.getenv("WORKER_RECONCILE_APPLY_ON_STARTUP", "false").lower() == "true"

app = FastAPI(title="SilentVoix Model Library Worker", version="1.0")


class ReconcileRequest(BaseModel):
    apply: bool = False
    prune_missing: bool = False
    activate_fallback: bool = True


def _ensure_registry() -> Dict[str, Any]:
    MODEL_LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
    if not REGISTRY_PATH.exists():
        default = {"models": [], "active_model_id": None}
        REGISTRY_PATH.write_text(json.dumps(default, ensure_ascii=True, indent=2), encoding="utf-8")
        return default
    try:
        data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"models": [], "active_model_id": None}
    if not isinstance(data, dict):
        return {"models": [], "active_model_id": None}
    if not isinstance(data.get("models"), list):
        data["models"] = []
    if "active_model_id" not in data:
        data["active_model_id"] = None
    return data


def _save_registry(data: Dict[str, Any]) -> None:
    tmp_path = REGISTRY_PATH.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8")
    tmp_path.replace(REGISTRY_PATH)


def _expected_paths(entry: Dict[str, Any]) -> Dict[str, str]:
    model_id = str(entry.get("id") or "").strip()
    model_file_name = str(entry.get("model_file_name") or "").strip()
    current_model_path = str(entry.get("model_path") or "").strip()
    suffix = Path(model_file_name).suffix.lower() or Path(current_model_path).suffix.lower() or ".bin"
    model_path = str((MODEL_LIBRARY_DIR / model_id / f"model{suffix}").resolve())
    metadata_path = str((MODEL_LIBRARY_DIR / model_id / "metadata.json").resolve())
    return {"model_path": model_path, "metadata_path": metadata_path}


def _reconcile(apply: bool, prune_missing: bool, activate_fallback: bool) -> Dict[str, Any]:
    registry = _ensure_registry()
    models = registry.get("models", [])

    changed_count = 0
    removed_ids: List[str] = []
    report_models: List[Dict[str, Any]] = []
    kept_models: List[Dict[str, Any]] = []

    for model in models:
        if not isinstance(model, dict):
            continue
        model_id = str(model.get("id") or "").strip()
        if not model_id:
            continue

        expected = _expected_paths(model)
        model_path = Path(expected["model_path"])
        metadata_path = Path(expected["metadata_path"])

        model_exists = model_path.exists() and model_path.is_file()
        metadata_exists = metadata_path.exists() and metadata_path.is_file()
        missing = not model_exists or not metadata_exists

        model_item = {
            "id": model_id,
            "model_exists": model_exists,
            "metadata_exists": metadata_exists,
            "missing": missing,
        }

        if apply:
            if str(model.get("model_path") or "") != expected["model_path"]:
                model["model_path"] = expected["model_path"]
                changed_count += 1
            if str(model.get("metadata_path") or "") != expected["metadata_path"]:
                model["metadata_path"] = expected["metadata_path"]
                changed_count += 1

            if missing and prune_missing:
                removed_ids.append(model_id)
                report_models.append(model_item)
                continue

        kept_models.append(model)
        report_models.append(model_item)

    if apply:
        registry["models"] = kept_models
        active_model_id = registry.get("active_model_id")
        kept_ids = {str(m.get("id")) for m in kept_models}
        if active_model_id not in kept_ids:
            if activate_fallback:
                registry["active_model_id"] = next(iter(kept_ids), None)
            else:
                registry["active_model_id"] = None
            changed_count += 1

        if changed_count > 0 or removed_ids:
            _save_registry(registry)

    return {
        "status": "success",
        "apply": apply,
        "prune_missing": prune_missing,
        "active_model_id": registry.get("active_model_id"),
        "models_total": len(models),
        "models_kept": len(kept_models),
        "models_removed": len(removed_ids),
        "removed_ids": removed_ids,
        "changes_applied": changed_count,
        "report": report_models,
    }


async def _background_reconcile_loop() -> None:
    await asyncio.sleep(2)
    while True:
        try:
            result = _reconcile(
                apply=True,
                prune_missing=RECONCILE_PRUNE_MISSING,
                activate_fallback=True,
            )
            logger.info(
                "Periodic reconcile done | total=%s kept=%s removed=%s changes=%s",
                result.get("models_total"),
                result.get("models_kept"),
                result.get("models_removed"),
                result.get("changes_applied"),
            )
        except Exception as exc:
            logger.warning("Periodic reconcile failed: %s", exc)
        await asyncio.sleep(max(30, RECONCILE_INTERVAL_SEC))


@app.on_event("startup")
async def startup_event() -> None:
    _ensure_registry()
    if RECONCILE_APPLY_ON_STARTUP:
        result = _reconcile(apply=True, prune_missing=RECONCILE_PRUNE_MISSING, activate_fallback=True)
        logger.info("Startup reconcile | changes=%s removed=%s", result.get("changes_applied"), result.get("models_removed"))
    asyncio.create_task(_background_reconcile_loop())


@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service": "worker-library",
        "version": "1.0",
        "model_library_dir": str(MODEL_LIBRARY_DIR),
    }


@app.post("/v1/reconcile")
def reconcile(req: ReconcileRequest) -> Dict[str, Any]:
    return _reconcile(apply=req.apply, prune_missing=req.prune_missing, activate_fallback=req.activate_fallback)


@app.get("/v1/reconcile")
def reconcile_preview() -> Dict[str, Any]:
    return _reconcile(apply=False, prune_missing=False, activate_fallback=True)
