from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import httpx

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


def _check_runtime_service(name: str, base_url: str) -> Dict[str, Any]:
    url = f"{str(base_url).rstrip('/')}/health"
    try:
        resp = httpx.get(url, timeout=2.5)
    except Exception as exc:
        return {"ok": False, "name": name, "url": url, "error": str(exc)}

    if resp.status_code >= 400:
        return {
            "ok": False,
            "name": name,
            "url": url,
            "status_code": int(resp.status_code),
            "error": "non-success status",
        }

    try:
        payload = resp.json()
    except Exception:
        payload = {}
    return {
        "ok": True,
        "name": name,
        "url": url,
        "status_code": int(resp.status_code),
        "payload": payload if isinstance(payload, dict) else {},
    }


def _runtime_services_preflight() -> Dict[str, Any]:
    enabled = bool(settings.USE_RUNTIME_SERVICES)
    if not enabled:
        return {"enabled": False}

    tf = _check_runtime_service("ml-tensorflow", settings.ML_TENSORFLOW_URL)
    torch = _check_runtime_service("ml-pytorch", settings.ML_PYTORCH_URL)
    return {
        "enabled": True,
        "tensorflow": tf,
        "pytorch": torch,
    }


def _worker_library_preflight() -> Dict[str, Any]:
    enabled = bool(settings.USE_WORKER_LIBRARY)
    if not enabled:
        return {"enabled": False}
    worker = _check_runtime_service("worker-library", settings.WORKER_LIBRARY_URL)
    return {"enabled": True, "worker_library": worker}


def run_runtime_preflight() -> Dict[str, Any]:
    return {
        "ml_runtime": settings.ML_RUNTIME,
        "use_runtime_services": settings.USE_RUNTIME_SERVICES,
        "ml_tensorflow_url": settings.ML_TENSORFLOW_URL,
        "ml_pytorch_url": settings.ML_PYTORCH_URL,
        "use_worker_library": settings.USE_WORKER_LIBRARY,
        "worker_library_url": settings.WORKER_LIBRARY_URL,
        "runtime_services": _runtime_services_preflight(),
        "worker_library": _worker_library_preflight(),
        "training_features_enabled": settings.TRAINING_FEATURES_ENABLED,
        "tensorflow": _import_version("tensorflow"),
        "torch": _import_version("torch"),
        "model_library": _read_registry(),
    }
