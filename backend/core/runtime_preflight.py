from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from core.settings import settings


def _import_version(module_name: str, attr_name: str = "__version__") -> Dict[str, Any]:
    try:
        module = __import__(module_name)
        version = getattr(module, attr_name, "unknown")
        return {"ok": True, "version": str(version)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _read_registry() -> Dict[str, Any]:
    registry_path = Path(settings.MODEL_LIBRARY_DIR) / "registry.json"
    if not registry_path.exists():
        return {
            "ok": True,
            "path": str(registry_path),
            "exists": False,
            "model_count": 0,
            "active_model_id": None,
            "runtime_status_counts": {"pass": 0, "fail": 0, "untested": 0},
        }

    try:
        data = json.loads(registry_path.read_text(encoding="utf-8"))
        models = data.get("models") if isinstance(data, dict) else []
        if not isinstance(models, list):
            models = []
        pass_count = 0
        fail_count = 0
        untested_count = 0
        for model in models:
            status = str((model or {}).get("runtime_status", {}).get("state", "")).strip().lower()
            if status == "pass":
                pass_count += 1
            elif status == "fail":
                fail_count += 1
            else:
                untested_count += 1
        return {
            "ok": True,
            "path": str(registry_path),
            "exists": True,
            "model_count": len(models),
            "active_model_id": (data or {}).get("active_model_id") if isinstance(data, dict) else None,
            "runtime_status_counts": {
                "pass": pass_count,
                "fail": fail_count,
                "untested": untested_count,
            },
        }
    except Exception as exc:
        return {"ok": False, "path": str(registry_path), "error": str(exc)}


def run_runtime_preflight() -> Dict[str, Any]:
    return {
        "ml_runtime": settings.ML_RUNTIME,
        "use_runtime_services": settings.USE_RUNTIME_SERVICES,
        "ml_tensorflow_url": settings.ML_TENSORFLOW_URL,
        "ml_pytorch_url": settings.ML_PYTORCH_URL,
        "training_features_enabled": settings.TRAINING_FEATURES_ENABLED,
        "tensorflow": _import_version("tensorflow"),
        "torch": _import_version("torch"),
        "model_library": _read_registry(),
    }
