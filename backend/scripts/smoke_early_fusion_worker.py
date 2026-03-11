#!/usr/bin/env python3
"""Smoke test for early fusion worker using fusion data npz samples."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

import numpy as np
import requests

DEFAULT_BASE_URL = "http://localhost:8095"
DEFAULT_DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "fusiondata"


def _jprint(title: str, resp: requests.Response) -> None:
    try:
        body = resp.json()
    except Exception:
        body = resp.text
    print(f"{title}: {resp.status_code} -> {json.dumps(body) if isinstance(body, dict) else body}")


def _post(base_url: str, payload: dict, timeout: float = 15.0) -> dict:
    resp = requests.post(f"{base_url}/predict", json=payload, timeout=timeout)
    _jprint("POST /predict", resp)
    resp.raise_for_status()
    return resp.json()


def _health(base_url: str) -> dict:
    resp = requests.get(f"{base_url}/health", timeout=10)
    _jprint("GET /health", resp)
    resp.raise_for_status()
    return resp.json()


def _iter_npz(label_dir: Path, max_per_label: int) -> Iterable[Path]:
    count = 0
    for path in sorted(label_dir.glob("*.npz")):
        yield path
        count += 1
        if count >= max_per_label:
            break


def _load_sample(path: Path) -> np.ndarray:
    with np.load(path, allow_pickle=True) as data:
        if "data" not in data.files:
            raise ValueError(f"{path} missing 'data' array")
        arr = data["data"]
    if arr.ndim != 2:
        raise ValueError(f"{path} expected 2D array, got {arr.ndim}D")
    return arr.astype(np.float32)


def run_smoke(base_url: str, data_dir: Path, max_per_label: int, session_prefix: str) -> None:
    health = _health(base_url)
    seq_len = int(health.get("sequence_length", 30))
    feat_dim = int(health.get("feature_dim", 74))

    if not data_dir.exists():
        raise FileNotFoundError(f"Data directory not found: {data_dir}")

    label_dirs = [p for p in sorted(data_dir.iterdir()) if p.is_dir()]
    if not label_dirs:
        raise FileNotFoundError(f"No label directories found in {data_dir}")

    total = 0
    for label_dir in label_dirs:
        label = label_dir.name
        for sample_path in _iter_npz(label_dir, max_per_label):
            total += 1
            session_id = f"{session_prefix}-{label}-{sample_path.stem}"

            _post(base_url, {"session_id": session_id, "reset": True})
            sample = _load_sample(sample_path)

            if sample.shape[0] < seq_len:
                raise ValueError(
                    f"{sample_path} has {sample.shape[0]} frames, expected at least {seq_len}"
                )
            if sample.shape[1] != feat_dim:
                raise ValueError(
                    f"{sample_path} has feature dim {sample.shape[1]}, expected {feat_dim}"
                )

            last_resp: dict | None = None
            for idx in range(seq_len):
                row = sample[idx].tolist()
                last_resp = _post(base_url, {"session_id": session_id, "fused_features": row})

            if not last_resp:
                raise RuntimeError("No response from worker")

            status = last_resp.get("status")
            if status != "success":
                raise RuntimeError(f"Prediction failed for {sample_path}: {last_resp}")

            gesture = last_resp.get("gesture")
            confidence = last_resp.get("confidence")
            if gesture is None or confidence is None:
                raise RuntimeError(f"Missing gesture/confidence for {sample_path}: {last_resp}")

            print(
                f"OK: {label}/{sample_path.name} -> {gesture} (conf={confidence:.4f})"
            )

    if total == 0:
        raise RuntimeError("No samples processed")
    print(f"Smoke test passed. Samples processed: {total}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Smoke test: early fusion worker using fusiondata npz samples",
    )
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Worker base URL")
    parser.add_argument(
        "--data-dir",
        default=str(DEFAULT_DATA_DIR),
        help="Path to fusion data directory (default: backend/data/fusiondata)",
    )
    parser.add_argument(
        "--max-per-label",
        type=int,
        default=1,
        help="Max samples per label directory",
    )
    parser.add_argument(
        "--session-prefix",
        default="smoke",
        help="Prefix for session IDs",
    )

    args = parser.parse_args()
    run_smoke(args.base_url.rstrip("/"), Path(args.data_dir), args.max_per_label, args.session_prefix)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Smoke test failed: {exc}")
        sys.exit(2)
