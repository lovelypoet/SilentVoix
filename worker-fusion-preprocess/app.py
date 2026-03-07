from __future__ import annotations

import csv
import io
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
logger = logging.getLogger("worker-fusion-preprocess")

JOB_DIR = Path(os.getenv("FUSION_PREPROCESS_JOB_DIR", "/app/data/fusion_preprocess_jobs")).resolve()
JOB_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="SilentVoix Fusion Preprocess Worker", version="1.0")


class AnalyzeOptions(BaseModel):
    trim_start_ms: Optional[int] = None
    trim_end_ms: Optional[int] = None
    max_abs_sensor_delta_ms: Optional[float] = None
    require_sensor_match: bool = True
    export_label: str = "processed"
    notes: str = ""


class AnalyzeRequest(BaseModel):
    source_file: str = Field(..., min_length=1)
    csv_text: str = Field(..., min_length=1)
    options: AnalyzeOptions = Field(default_factory=AnalyzeOptions)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _job_path(job_id: str) -> Path:
    return JOB_DIR / f"{job_id}.json"


def _read_csv(csv_text: str) -> tuple[list[str], list[dict[str, str]]]:
    try:
        reader = csv.DictReader(io.StringIO(csv_text))
        header = [str(name).strip() for name in (reader.fieldnames or []) if str(name).strip()]
        if not header:
            raise ValueError("CSV header is missing.")
        rows = []
        for row in reader:
            rows.append({key: (row.get(key, "") if row else "") for key in header})
        if not rows:
            raise ValueError("CSV contains no data rows.")
        return header, rows
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV: {exc}") from exc


def _count_landmark_dims(header: list[str], prefix: str) -> int:
    columns = set(header)
    dim = 0
    for idx in range(21):
        for axis in ("x", "y", "z"):
            if f"{prefix}_{axis}{idx}" in columns:
                dim += 1
    return dim


def _infer_schema_id(header: list[str]) -> str:
    columns = set(header)
    has_sensor = any(col.startswith("sensor_") for col in columns)
    if has_sensor:
        if any(col.startswith("sensor_left_") or col.startswith("sensor_right_") for col in columns):
            return "fusion_dual"
        return "fusion_single"
    if _count_landmark_dims(header, "L") + _count_landmark_dims(header, "R") > 0:
        return "cv_dual" if _count_landmark_dims(header, "R") == 63 else "cv_single"
    return "unknown"


def _first_present(header: list[str], *candidates: str) -> str:
    for candidate in candidates:
        if candidate in header:
            return candidate
    return ""


def _safe_float(value: Any) -> Optional[float]:
    try:
        num = float(str(value))
    except (TypeError, ValueError):
        return None
    if num != num or num in (float("inf"), float("-inf")):
        return None
    return num


def _safe_int(value: Any) -> Optional[int]:
    parsed = _safe_float(value)
    if parsed is None:
        return None
    return int(parsed)


def _row_has_sensor_match(row: dict[str, str]) -> bool:
    source = str(row.get("capture_sensor_source", "")).strip().lower()
    return source not in {"", "none", "unknown"}


def _row_missing_hands(row: dict[str, str], schema_id: str) -> bool:
    left_missing = _safe_int(row.get("L_exist")) == 0 if "L_exist" in row else False
    if schema_id == "fusion_single":
        return left_missing
    right_missing = _safe_int(row.get("R_exist")) == 0 if "R_exist" in row else False
    return left_missing and right_missing


def _build_processed_csv(header: list[str], rows: list[dict[str, str]]) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=header, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key, "") for key in header})
    return output.getvalue()


def _evaluate_status(max_abs_delta_ms: Optional[float], sensor_match_ratio: float, missing_frame_ratio: float) -> tuple[str, list[str]]:
    reasons: list[str] = []
    status = "pass"

    if max_abs_delta_ms is None:
        status = "reject"
        reasons.append("sensor_match_delta_ms is missing or invalid")
    elif max_abs_delta_ms > 2000:
        status = "reject"
        reasons.append("max abs sensor delta exceeds 2000 ms")
    elif max_abs_delta_ms > 500:
        status = "warning"
        reasons.append("max abs sensor delta exceeds 500 ms")

    if sensor_match_ratio < 0.5:
        status = "reject"
        reasons.append("sensor match ratio is below 0.5")
    elif sensor_match_ratio < 0.85 and status == "pass":
        status = "warning"
        reasons.append("sensor match ratio is below 0.85")

    if missing_frame_ratio > 0.35:
        status = "reject"
        reasons.append("missing frame ratio exceeds 0.35")
    elif missing_frame_ratio > 0.15 and status == "pass":
        status = "warning"
        reasons.append("missing frame ratio exceeds 0.15")

    if not reasons and status == "pass":
        reasons.append("sample passed current fusion validation thresholds")

    return status, reasons


def _analyze(req: AnalyzeRequest) -> Dict[str, Any]:
    header, rows = _read_csv(req.csv_text)
    schema_id = _infer_schema_id(header)
    ts_key = _first_present(header, "timestamp_ms", "timestamp")
    delta_key = _first_present(header, "sensor_match_delta_ms")
    if not ts_key:
        raise HTTPException(status_code=400, detail="CSV is missing a timestamp column.")

    trim_start = req.options.trim_start_ms
    trim_end = req.options.trim_end_ms
    max_abs_delta = req.options.max_abs_sensor_delta_ms

    raw_timestamps = [_safe_int(row.get(ts_key)) for row in rows]
    valid_raw_timestamps = [value for value in raw_timestamps if value is not None]
    raw_deltas = [_safe_float(row.get(delta_key)) for row in rows] if delta_key else []
    valid_raw_deltas = [abs(value) for value in raw_deltas if value is not None]

    processed_rows: list[dict[str, str]] = []
    for row in rows:
        ts = _safe_int(row.get(ts_key))
        if ts is None:
            continue
        if trim_start is not None and ts < trim_start:
            continue
        if trim_end is not None and ts > trim_end:
            continue
        if req.options.require_sensor_match and not _row_has_sensor_match(row):
            continue
        if delta_key and max_abs_delta is not None:
            delta_value = _safe_float(row.get(delta_key))
            if delta_value is None or abs(delta_value) > max_abs_delta:
                continue
        processed_rows.append(row)

    processed_timestamps = [_safe_int(row.get(ts_key)) for row in processed_rows]
    valid_processed_timestamps = [value for value in processed_timestamps if value is not None]
    processed_deltas = [_safe_float(row.get(delta_key)) for row in processed_rows] if delta_key else []
    valid_processed_deltas = [abs(value) for value in processed_deltas if value is not None]

    missing_frame_ratio = (
        sum(1 for row in processed_rows if _row_missing_hands(row, schema_id)) / len(processed_rows)
        if processed_rows else 1.0
    )
    sensor_match_ratio = (
        sum(1 for row in processed_rows if _row_has_sensor_match(row)) / len(processed_rows)
        if processed_rows else 0.0
    )
    status, reasons = _evaluate_status(
        max(valid_processed_deltas) if valid_processed_deltas else None,
        sensor_match_ratio,
        missing_frame_ratio,
    )

    metadata = {
        "source_file": req.source_file,
        "schema_id": schema_id,
        "timestamp_column": ts_key,
        "delta_column": delta_key or None,
        "crop_rules": req.options.model_dump(),
        "source_summary": {
            "row_count": len(rows),
            "start_ms": min(valid_raw_timestamps) if valid_raw_timestamps else None,
            "end_ms": max(valid_raw_timestamps) if valid_raw_timestamps else None,
            "max_abs_sensor_match_delta_ms": max(valid_raw_deltas) if valid_raw_deltas else None,
        },
        "processed_summary": {
            "row_count": len(processed_rows),
            "dropped_rows": max(0, len(rows) - len(processed_rows)),
            "start_ms": min(valid_processed_timestamps) if valid_processed_timestamps else None,
            "end_ms": max(valid_processed_timestamps) if valid_processed_timestamps else None,
            "avg_abs_sensor_match_delta_ms": round(sum(valid_processed_deltas) / len(valid_processed_deltas), 2) if valid_processed_deltas else None,
            "max_abs_sensor_match_delta_ms": max(valid_processed_deltas) if valid_processed_deltas else None,
            "sensor_match_ratio": round(sensor_match_ratio, 4),
            "missing_frame_ratio": round(missing_frame_ratio, 4),
        },
        "validation": {
            "cv_spike_detected": bool(valid_processed_timestamps),
            "sensor_spike_detected": sensor_match_ratio > 0,
            "offset_ms": round(sum(processed_deltas) / len(processed_deltas)) if processed_deltas else None,
            "max_abs_sensor_match_delta_ms": max(valid_processed_deltas) if valid_processed_deltas else None,
            "sensor_match_ratio": round(sensor_match_ratio, 4),
            "missing_frame_ratio": round(missing_frame_ratio, 4),
            "status": status,
            "reasons": reasons,
        },
        "notes": req.options.notes,
        "processed_at": _utc_now(),
    }

    return {
        "header": header,
        "processed_rows_preview": processed_rows[:20],
        "processed_csv_text": _build_processed_csv(header, processed_rows),
        "metadata": metadata,
    }


def _save_job(job_id: str, payload: Dict[str, Any]) -> None:
    _job_path(job_id).write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def _load_job(job_id: str) -> Dict[str, Any]:
    path = _job_path(job_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Preprocess job not found: {job_id}")
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/health")
def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service": "worker-fusion-preprocess",
        "version": "1.0",
        "job_dir": str(JOB_DIR),
    }


@app.post("/v1/jobs/analyze")
def create_analyze_job(req: AnalyzeRequest) -> Dict[str, Any]:
    job_id = str(uuid4())
    created_at = _utc_now()
    logger.info("Starting fusion preprocess job %s for %s", job_id, req.source_file)
    result = _analyze(req)
    payload = {
        "job_id": job_id,
        "status": "completed",
        "created_at": created_at,
        "completed_at": _utc_now(),
        "result": result,
    }
    _save_job(job_id, payload)
    return payload


@app.get("/v1/jobs/{job_id}")
def get_job(job_id: str) -> Dict[str, Any]:
    return _load_job(job_id)
