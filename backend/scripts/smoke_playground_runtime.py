#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import requests


DEFAULT_LABELS = ["Hello", "Yes", "No", "We", "Are", "Students", "Rest"]


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def backend_root() -> Path:
    return repo_root() / "backend"


def default_model_path() -> Path:
    tflite_candidate = backend_root() / "AI" / "gesture_model.tflite"
    if tflite_candidate.exists():
        return tflite_candidate
    sensor_candidate = backend_root() / "best_model_processed_sensor.pth"
    if sensor_candidate.exists():
        return sensor_candidate
    cv_candidate = backend_root() / "best_model_processed.pth"
    if cv_candidate.exists():
        return cv_candidate
    raise FileNotFoundError("No default .pth model found under backend/")


def infer_input_dim(model_path: Path) -> int:
    return 11 if "sensor" in model_path.name.lower() else 63


def infer_modality(input_dim: int) -> str:
    return "sensor" if input_dim in (11, 22) else "cv"


def infer_export_format(model_path: Path) -> str:
    suffix = model_path.suffix.lower()
    if suffix == ".tflite":
        return "tflite"
    if suffix == ".keras":
        return "keras"
    if suffix == ".h5":
        return "h5"
    if suffix in {".pth", ".pt"}:
        return "pytorch"
    raise ValueError(f"Unsupported model extension for smoke script: {suffix}")


def build_metadata(model_path: Path, input_dim: int) -> Dict[str, Any]:
    modality = infer_modality(input_dim)
    export_format = infer_export_format(model_path)
    return {
        "model_name": f"smoke-{model_path.stem}",
        "model_family": export_format,
        "input_spec": {"input_dim": input_dim, "shape": [1, input_dim], "modality": modality},
        "labels": DEFAULT_LABELS,
        "modality": modality,
        "export_format": export_format,
        "version": "smoke-1",
        "precision": 0.0,
        "recall": 0.0,
        "f1": 0.0,
    }


def request_json(
    method: str,
    url: str,
    headers: Dict[str, str],
    *,
    json_body: Dict[str, Any] | None = None,
    files: Dict[str, Any] | None = None,
    timeout: float = 30.0,
) -> Dict[str, Any]:
    resp = requests.request(method, url, headers=headers, json=json_body, files=files, timeout=timeout)
    try:
        payload = resp.json()
    except Exception:
        payload = {"raw": resp.text}
    if resp.status_code >= 400:
        raise RuntimeError(f"{method} {url} failed ({resp.status_code}): {payload}")
    if not isinstance(payload, dict):
        raise RuntimeError(f"{method} {url} returned non-object JSON: {payload}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test: upload -> activate -> runtime-check -> predict")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Backend base URL")
    parser.add_argument("--api-key", default=os.getenv("SECRET_KEY", "change-me-in-prod"), help="X-API-KEY value")
    parser.add_argument("--model-path", default=str(default_model_path()), help="Path to model artifact (.pth/.pt)")
    parser.add_argument("--keep-model", action="store_true", help="Keep uploaded model in registry after smoke test")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    model_path = Path(args.model_path).resolve()
    if not model_path.exists():
        raise FileNotFoundError(f"Model not found: {model_path}")

    headers = {"x-api-key": args.api_key}
    attempted_dims: List[int] = [infer_input_dim(model_path)]
    for candidate in (11, 63):
        if candidate not in attempted_dims:
            attempted_dims.append(candidate)

    last_error: Exception | None = None
    for input_dim in attempted_dims:
        modality = infer_modality(input_dim)
        predict_endpoint = "/playground/predict/sensor" if modality == "sensor" else "/playground/predict/cv"
        predict_field = "sensor_values" if modality == "sensor" else "cv_values"
        uploaded_model_id = None

        metadata = build_metadata(model_path, input_dim)
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as tmp:
            json.dump(metadata, tmp, ensure_ascii=True, indent=2)
            metadata_path = Path(tmp.name)

        try:
            with model_path.open("rb") as model_fp, metadata_path.open("rb") as metadata_fp:
                upload = request_json(
                    "POST",
                    f"{base_url}/playground/models/upload",
                    headers,
                    files={
                        "model_file": (model_path.name, model_fp, "application/octet-stream"),
                        "metadata_file": ("metadata.json", metadata_fp, "application/json"),
                    },
                )
            uploaded_model_id = str(upload.get("active_model_id") or "")
            if not uploaded_model_id:
                raise RuntimeError(f"Upload response missing active_model_id: {upload}")

            activate = request_json("POST", f"{base_url}/playground/models/{uploaded_model_id}/activate", headers)
            if str(activate.get("active_model_id") or "") != uploaded_model_id:
                raise RuntimeError(f"Activation mismatch: expected {uploaded_model_id}, got {activate}")

            runtime_check = request_json(
                "GET",
                f"{base_url}/playground/models/{uploaded_model_id}/runtime-check",
                headers,
            )
            if str(runtime_check.get("status", "")).lower() != "success":
                raise RuntimeError(f"Runtime-check failed: {runtime_check}")

            vector: List[float] = [0.0] * input_dim
            predict = request_json(
                "POST",
                f"{base_url}{predict_endpoint}",
                headers,
                json_body={predict_field: vector, "model_id": uploaded_model_id},
            )
            prediction = predict.get("prediction")
            if not isinstance(prediction, dict):
                raise RuntimeError(f"Prediction payload missing: {predict}")
            if "label" not in prediction or "confidence" not in prediction:
                raise RuntimeError(f"Prediction contract mismatch: {prediction}")

            print("Smoke test passed")
            print(f"- model_id: {uploaded_model_id}")
            print(f"- modality: {modality}")
            print(f"- input_dim: {input_dim}")
            print(f"- label: {prediction.get('label')}")
            print(f"- confidence: {prediction.get('confidence')}")
            return 0

        except Exception as exc:
            last_error = exc
            print(f"- attempt failed with input_dim={input_dim}: {exc}", file=sys.stderr)

        finally:
            try:
                metadata_path.unlink(missing_ok=True)
            except Exception:
                pass

            if uploaded_model_id and not args.keep_model:
                try:
                    request_json("DELETE", f"{base_url}/playground/models/{uploaded_model_id}", headers)
                    print(f"- cleanup: deleted {uploaded_model_id}")
                except Exception as exc:
                    print(f"- cleanup warning: {exc}", file=sys.stderr)

    if last_error:
        raise last_error
    raise RuntimeError("Smoke test ended without executing any attempts")


if __name__ == "__main__":
    raise SystemExit(main())
