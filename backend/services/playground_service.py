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

from AI.runtime_adapter import (
    SUPPORTED_EXPORT_FORMATS,
    SUPPORTED_MODEL_EXTENSIONS,
    load_runtime,
    normalize_export_format,
    predict as predict_runtime,
    validate_export_and_extension,
)
from core.settings import settings

logger = logging.getLogger("signglove.playground")

class PlaygroundService:
    def __init__(self):
        self._cache_lock = threading.Lock()
        self._model_cache: Dict[str, Dict[str, Any]] = {}
        self._allowed_modalities = {"cv", "sensor"}
        self._remote_model_library_root = Path("/shared/model_library")

    def get_models_root(self) -> Path:
        root = Path(settings.MODEL_LIBRARY_DIR)
        root.mkdir(parents=True, exist_ok=True)
        return root

    def get_registry_path(self) -> Path:
        return self.get_models_root() / "registry.json"

    def load_registry(self) -> Dict[str, Any]:
        path = self.get_registry_path()
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
            
            # Maintenance update for paths if they moved.
            changed = False
            root = self.get_models_root().resolve()
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
                if not metadata.get("modality"):
                    input_dim = int(entry.get("input_dim") or 0)
                    inferred = self.infer_modality_from_dim(input_dim)
                    if inferred:
                        metadata["modality"] = inferred
                        input_spec = metadata.get("input_spec")
                        if isinstance(input_spec, dict):
                            input_spec["modality"] = inferred
                        changed = True
            
            if changed:
                self.save_registry(data)
            return data
        except Exception:
            return {"models": [], "active_model_id": None}

    def save_registry(self, data: Dict[str, Any]) -> None:
        path = self.get_registry_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_suffix(".json.tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=True, indent=2)
        tmp_path.replace(path)

    def get_model_entry(self, registry: Dict[str, Any], model_id: str) -> Dict[str, Any]:
        entry = next((m for m in registry.get("models", []) if m.get("id") == model_id), None)
        if not entry:
            raise ValueError(f"Model not found: {model_id}")
        return entry

    def infer_modality_from_dim(self, input_dim: int) -> Optional[str]:
        if input_dim in {63, 126}:
            return "cv"
        if input_dim in {11, 22}:
            return "sensor"
        return None

    def get_entry_modality(self, entry: Dict[str, Any]) -> str:
        metadata = entry.get("metadata") or {}
        raw = str(metadata.get("modality") or "").strip().lower()
        if raw in self._allowed_modalities:
            return raw
        inferred = self.infer_modality_from_dim(int(entry.get("input_dim") or 0))
        return inferred or ""

    def validate_metadata(self, metadata: Dict[str, Any], model_suffix: str) -> None:
        required = ["model_name", "model_family", "input_spec", "labels", "export_format", "version", "precision", "recall", "f1"]
        missing = [key for key in required if key not in metadata]
        if missing:
            raise ValueError(f"Metadata missing required fields: {', '.join(missing)}")
        if not isinstance(metadata.get("labels"), list) or not metadata["labels"]:
            raise ValueError("metadata.labels must be a non-empty array")
        if not isinstance(metadata.get("input_spec"), dict):
            raise ValueError("metadata.input_spec must be an object")
        for metric_name in ("precision", "recall", "f1"):
            if not isinstance(metadata.get(metric_name), (int, float)):
                raise ValueError(f"metadata.{metric_name} must be numeric")
        export_format = str(metadata.get("export_format", "")).strip().lower()
        validate_export_and_extension(model_suffix, export_format)

    def input_dim_from_metadata(self, metadata: Dict[str, Any]) -> int:
        input_spec = metadata.get("input_spec") or {}
        if not isinstance(input_spec, dict):
            raise ValueError("metadata.input_spec must be object")

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

        raise ValueError("Unable to infer input dimension from metadata.input_spec")

    def resolve_model_modality(self, metadata: Dict[str, Any], input_dim: int) -> Optional[str]:
        input_spec = metadata.get("input_spec") or {}
        raw = metadata.get("modality") or input_spec.get("modality")
        if raw is not None:
            modality = str(raw).strip().lower()
            if modality not in self._allowed_modalities:
                raise ValueError(f"Unsupported modality: {modality}. Allowed: cv, sensor")
            return modality
        return self.infer_modality_from_dim(input_dim)

    def load_model_runtime(self, model_entry: Dict[str, Any]) -> Dict[str, Any]:
        model_path = Path(model_entry["model_path"]).resolve()
        if not model_path.exists():
            raise FileNotFoundError(f"Model file not found: {model_path.name}")

        model_id = str(model_entry["id"])
        model_mtime = model_path.stat().st_mtime
        with self._cache_lock:
            cached = self._model_cache.get(model_id)
            if cached and cached.get("mtime") == model_mtime:
                return cached

        export_format = str(model_entry["metadata"]["export_format"]).lower()
        is_state_dict = bool(model_entry["metadata"].get("is_state_dict", False))
        has_model_class = bool(model_entry["metadata"].get("has_model_class", False))
        
        runtime: Dict[str, Any] = load_runtime(
            str(model_path), 
            export_format,
            is_state_dict=is_state_dict,
            has_model_class=has_model_class
        )
        runtime["mtime"] = model_mtime
        runtime["export_format"] = normalize_export_format(export_format)
        runtime["metadata"] = model_entry.get("metadata", {})

        with self._cache_lock:
            self._model_cache[model_id] = runtime
        return runtime

    def predict_with_runtime(self, runtime: Dict[str, Any], cv_values: np.ndarray) -> np.ndarray:
        return predict_runtime(runtime, cv_values)

    def coerce_input_vector(self, values: List[float], expected_dim: int, field_name: str) -> np.ndarray:
        vector = np.asarray(values, dtype=np.float32).reshape(-1)
        if expected_dim <= 0:
            raise ValueError("Invalid model input dimension")
        if vector.shape[0] != expected_dim:
            raise ValueError(f"{field_name} length mismatch: expected {expected_dim}, got {vector.shape[0]}")
        if not np.isfinite(vector).all():
            raise ValueError(f"{field_name} contains non-finite values")
        return vector

    def _wrist_center_v1(self, vector: np.ndarray, start_idx: int = 0) -> None:
        if vector.size < start_idx + 3:
            return
        anchor_x = float(vector[start_idx])
        anchor_y = float(vector[start_idx + 1])
        anchor_z = float(vector[start_idx + 2])
        # 21 landmarks, 3 coordinates each
        for i in range(21):
            offset = start_idx + i * 3
            if offset + 2 < vector.size:
                vector[offset] -= anchor_x
                vector[offset + 1] -= anchor_y
                vector[offset + 2] -= anchor_z

    def _linear_temporal_interpolate(self, frames: List[np.ndarray], target_len: int, feature_dim: int) -> np.ndarray:
        if not frames:
            return np.zeros((target_len, feature_dim), dtype=np.float32)
        
        source_len = len(frames)
        if source_len == target_len:
            return np.stack(frames)
        
        if source_len == 1:
            return np.tile(frames[0], (target_len, 1))

        out = np.zeros((target_len, feature_dim), dtype=np.float32)
        max_idx = source_len - 1
        for i in range(target_len):
            t = (i * max_idx) / max(1, target_len - 1)
            left_idx = int(np.floor(t))
            right_idx = min(max_idx, int(np.ceil(t)))
            alpha = t - left_idx
            
            left = frames[left_idx]
            right = frames[right_idx]
            out[i] = left + (right - left) * alpha
            
        return out

    def preprocess_cv_sequence(self, frames: List[List[float]], metadata: Dict[str, Any]) -> np.ndarray:
        input_spec = metadata.get("input_spec", {})
        preprocess_profile = str(input_spec.get("preprocess_profile") or "").lower()
        sequence_length = int(input_spec.get("sequence_length") or 1)
        feature_dim = int(input_spec.get("feature_dim") or 63)
        
        # 1. Convert to numpy frames
        np_frames = [np.asarray(f, dtype=np.float32) for f in frames if len(f) >= feature_dim]
        
        # 2. Apply normalization (centering)
        if "wrist_center" in preprocess_profile:
            for f in np_frames:
                if f.size >= 63:
                    self._wrist_center_v1(f, 0)
                if f.size >= 126:
                    self._wrist_center_v1(f, 63)

        # 3. Interpolate
        if sequence_length > 1:
            # Temporal model
            sequence = self._linear_temporal_interpolate(np_frames, sequence_length, feature_dim)
            return sequence.reshape(-1)
        else:
            # Single frame model (return last frame)
            if not np_frames:
                return np.zeros(feature_dim, dtype=np.float32)
            last = np_frames[-1]
            if last.size > feature_dim:
                return last[:feature_dim]
            elif last.size < feature_dim:
                return np.pad(last, (0, feature_dim - last.size))
            return last

    def normalize_probs(self, probs: np.ndarray) -> np.ndarray:
        work = np.asarray(probs, dtype=np.float32).reshape(-1)
        if work.size == 0:
            raise ValueError("Model returned empty prediction")
        if np.any(~np.isfinite(work)):
            raise ValueError("Model returned non-finite prediction values")
        if np.any(work < 0) or work.sum() <= 0:
            exp = np.exp(work - np.max(work))
            denom = float(np.sum(exp))
            if denom <= 0:
                raise ValueError("Model returned invalid logits for normalization")
            return exp / denom
        total = float(np.sum(work))
        if total <= 0:
            raise ValueError("Model returned invalid probability sum")
        return work / total

    def trigger_worker_reconcile(self, reason: str) -> None:
        if not bool(settings.USE_WORKER_LIBRARY):
            return
        base = str(settings.WORKER_LIBRARY_URL).rstrip("/")
        url = f"{base}/v1/reconcile"
        payload = {"apply": True, "prune_missing": False, "activate_fallback": True}
        try:
            httpx.post(url, json=payload, timeout=2.5)
            logger.info("Worker reconcile triggered after %s", reason)
        except Exception as exc:
            logger.warning("Worker reconcile request failed after %s: %s", reason, exc)

    # Remote runtime service helpers
    def get_runtime_service_url(self, export_format: str) -> str:
        normalized = normalize_export_format(export_format)
        if normalized in {"tflite", "keras", "h5"}:
            return str(settings.ML_TENSORFLOW_URL).rstrip("/")
        if normalized == "pytorch":
            return str(settings.ML_PYTORCH_URL).rstrip("/")
        raise ValueError(f"Unsupported export format: {export_format}")

    def get_runtime_service_model_path(self, entry: Dict[str, Any]) -> str:
        local_path = Path(str(entry.get("model_path", ""))).resolve()
        root = self.get_models_root().resolve()
        rel = local_path.relative_to(root)
        return str(self._remote_model_library_root / rel)

    def get_runtime_payload(self, entry: Dict[str, Any], input_vector: Optional[np.ndarray] = None) -> Dict[str, Any]:
        metadata = entry.get("metadata", {}) or {}
        payload: Dict[str, Any] = {
            "model_id": str(entry.get("id", "")),
            "model_path": self.get_runtime_service_model_path(entry),
            "export_format": str(metadata.get("export_format", "")),
            "input_dim": int(entry.get("input_dim") or 0),
            "labels": [str(v) for v in (metadata.get("labels") or [])],
            "modality": self.get_entry_modality(entry) or None,
            "is_state_dict": bool(metadata.get("is_state_dict", False)),
            "has_model_class": bool(metadata.get("has_model_class", False)),
        }
        if input_vector is not None:
            payload["input_vector"] = [float(v) for v in input_vector.tolist()]
        return payload

    def call_runtime_service(self, entry: Dict[str, Any], endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        service_url = self.get_runtime_service_url(str(entry.get("metadata", {}).get("export_format", "")))
        url = f"{service_url}{endpoint}"
        resp = httpx.post(url, json=payload, timeout=10.0)
        
        try:
            data = resp.json()
        except Exception:
            raise RuntimeError("Runtime service returned invalid JSON")

        if resp.status_code >= 400:
            detail = data.get("message") if isinstance(data, dict) else f"Runtime service HTTP {resp.status_code}"
            raise RuntimeError(str(detail))
        if isinstance(data, dict) and data.get("status") == "error":
            detail = str(data.get("message") or "Runtime service returned an error")
            raise RuntimeError(detail)
        return data

    def remote_runtime_check(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        payload = self.get_runtime_payload(entry)
        return self.call_runtime_service(entry, "/v1/runtime-check", payload)

    def remote_predict(self, entry: Dict[str, Any], vector: np.ndarray) -> Dict[str, Any]:
        payload = self.get_runtime_payload(entry, input_vector=vector)
        return self.call_runtime_service(entry, "/v1/predict", payload)

    def perform_runtime_check(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        expected_dim = int(entry.get("input_dim") or 0)
        if expected_dim <= 0:
            raise ValueError("Invalid model input dimension")

        if bool(settings.USE_RUNTIME_SERVICES):
            result = self.remote_runtime_check(entry)
            output_dim = int(result.get("output_dim") or 0)
            if output_dim <= 0:
                raise RuntimeError("Runtime service returned invalid output dimension")
            return {
                "status": "success",
                "model_id": str(entry.get("id", "")),
                "model_name": entry.get("display_name"),
                "export_format": str(entry.get("metadata", {}).get("export_format", "")),
                "input_dim": expected_dim,
                "output_dim": output_dim,
                "message": str(result.get("message") or "Runtime load and dry-run inference succeeded"),
            }

        runtime = self.load_model_runtime(entry)
        probe = np.zeros((expected_dim,), dtype=np.float32)
        probs = self.predict_with_runtime(runtime, probe)
        probs = np.asarray(probs, dtype=np.float32).reshape(-1)
        if probs.size == 0:
            raise RuntimeError("Model runtime-check returned empty output")

        return {
            "status": "success",
            "model_id": str(entry.get("id", "")),
            "model_name": entry.get("display_name"),
            "export_format": str(entry.get("metadata", {}).get("export_format", "")),
            "input_dim": expected_dim,
            "output_dim": int(probs.shape[0]),
            "message": "Runtime load and dry-run inference succeeded",
        }

    def clear_cache(self, model_id: Optional[str] = None) -> None:
        with self._cache_lock:
            if model_id:
                self._model_cache.pop(model_id, None)
            else:
                self._model_cache.clear()

# Singleton instance
playground_service = PlaygroundService()
