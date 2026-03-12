import time
import asyncio
import os
import csv
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi import HTTPException, Query
from api.core.settings import settings
from api.ingestion.sync_stream import SyncStreamBuffer, load_sensor_samples

ws_router = APIRouter(prefix="/ws", tags=["WebSocket"])
http_router = APIRouter(prefix="/sync", tags=["Sync"])

_last_payload = None
_last_update = 0.0
_payload_lock = asyncio.Lock()

SINGLE_SENSOR_HEADER = [
    "timestamp_ms",
    "ax",
    "ay",
    "az",
    "gx",
    "gy",
    "gz",
    "f1",
    "f2",
    "f3",
    "f4",
    "f5",
    "label",
]

DUAL_SENSOR_HEADER = [
    "session_id",
    "label",
    "timestamp",
    "timestamp_ms",
    "left_flex_1",
    "left_flex_2",
    "left_flex_3",
    "left_flex_4",
    "left_flex_5",
    "left_acc_1",
    "left_acc_2",
    "left_acc_3",
    "left_gyro_1",
    "left_gyro_2",
    "left_gyro_3",
    "right_flex_1",
    "right_flex_2",
    "right_flex_3",
    "right_flex_4",
    "right_flex_5",
    "right_acc_1",
    "right_acc_2",
    "right_acc_3",
    "right_gyro_1",
    "right_gyro_2",
    "right_gyro_3",
]


def _sensor_csv_path(mode: str) -> str:
    filename = "Students.csv" if mode == "single" else "dual_hand_raw_data.csv"
    return os.path.join(settings.DATA_DIR, filename)


def _normalize_header(row: dict, mode: str) -> dict:
    if mode == "single":
        ordered = SINGLE_SENSOR_HEADER
    else:
        ordered = DUAL_SENSOR_HEADER
    return {key: row.get(key, "") for key in ordered}


@ws_router.websocket("/sync")
async def websocket_sync_stream(websocket: WebSocket):
    await websocket.accept()
    buffer = SyncStreamBuffer(max_points=60)
    mode = "single"
    last_send = 0.0

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "cv_sample")

            if msg_type == "configure":
                mode = data.get("mode", mode)
                if mode not in ["single", "dual"]:
                    mode = "single"
                await websocket.send_json({"type": "ack", "mode": mode})
                continue

            if msg_type == "cv_sample":
                velocity = data.get("velocity")
                if velocity is not None:
                    timestamp_ms = data.get("timestamp_ms")
                    parsed_ts = None
                    if timestamp_ms is not None:
                        try:
                            parsed_ts = int(timestamp_ms)
                        except (TypeError, ValueError):
                            parsed_ts = None
                    buffer.add_cv_sample(float(velocity), parsed_ts)

            now = time.time()
            if msg_type == "tick" or (now - last_send) >= 0.1:
                sensor_samples = load_sensor_samples(mode=mode, limit=200, max_points=60)
                sensor_stats = buffer.compute_sensor_stats(sensor_samples)
                sensor_series = [float(item["value"]) for item in sensor_samples]
                sensor_timestamps = [int(item["timestamp_ms"]) for item in sensor_samples]

                cv_samples = buffer.get_cv_samples()
                cv_stats = buffer.compute_cv_stats(cv_samples)
                cv_series = [float(item["value"]) for item in cv_samples]
                cv_timestamps = [int(item["timestamp_ms"]) for item in cv_samples]
                sync_offset_ms = None
                if sensor_stats["spike_timestamp_ms"] is not None and cv_stats["spike_timestamp_ms"] is not None:
                    sync_offset_ms = int(sensor_stats["spike_timestamp_ms"] - cv_stats["spike_timestamp_ms"])
                payload = {
                    "type": "sync_series",
                    "mode": mode,
                    "offset_ms": sync_offset_ms,
                    "sensor": {
                        "series": sensor_series,
                        "timestamps_ms": sensor_timestamps,
                        "threshold": sensor_stats["threshold"],
                        "spike_index": sensor_stats["spike_index"],
                        "spike_active": sensor_stats["spike_active"],
                        "spike_timestamp_ms": sensor_stats["spike_timestamp_ms"],
                    },
                    "cv": {
                        "series": cv_series,
                        "timestamps_ms": cv_timestamps,
                        "threshold": cv_stats["threshold"],
                        "spike_index": cv_stats["spike_index"],
                        "spike_active": cv_stats["spike_active"],
                        "spike_timestamp_ms": cv_stats["spike_timestamp_ms"],
                    },
                }
                async with _payload_lock:
                    global _last_payload, _last_update
                    _last_payload = payload
                    _last_update = now
                await websocket.send_json(payload)
                last_send = now

    except WebSocketDisconnect:
        pass
    except Exception:
        try:
            await websocket.close()
        except Exception:
            pass


@http_router.get("/series")
async def get_sync_series():
    """
    Return the latest merged sensor + CV series for replay/offline analysis.
    """
    async with _payload_lock:
        if _last_payload is None:
            return {"status": "empty", "last_update": None, "data": None}
        return {"status": "ok", "last_update": _last_update, "data": _last_payload}


@http_router.get("/sensor-window")
async def get_sensor_window(
    mode: str = Query("single"),
    start_ms: int = Query(..., ge=0),
    end_ms: int = Query(..., ge=0),
    pad_ms: int = Query(0, ge=0, le=10000),
):
    if mode not in {"single", "dual"}:
        raise HTTPException(status_code=400, detail="mode must be 'single' or 'dual'")
    if end_ms < start_ms:
        raise HTTPException(status_code=400, detail="end_ms must be >= start_ms")

    csv_path = _sensor_csv_path(mode)
    if not os.path.exists(csv_path):
        return {"status": "ok", "mode": mode, "header": SINGLE_SENSOR_HEADER if mode == "single" else DUAL_SENSOR_HEADER, "rows": []}

    start_bound = start_ms - pad_ms
    end_bound = end_ms + pad_ms
    rows = []
    expected_header = SINGLE_SENSOR_HEADER if mode == "single" else DUAL_SENSOR_HEADER

    try:
        with open(csv_path, "r", encoding="utf-8", errors="ignore", newline="") as f:
            reader = csv.DictReader(f)
            file_headers = reader.fieldnames or []
            for row in reader:
                ts_raw = row.get("timestamp_ms")
                if ts_raw is None:
                    continue
                try:
                    ts = int(float(ts_raw))
                except (TypeError, ValueError):
                    continue
                if start_bound <= ts <= end_bound:
                    normalized = _normalize_header(row, mode)
                    normalized["timestamp_ms"] = str(ts)
                    rows.append(normalized)
            if file_headers:
                expected_header = [h for h in file_headers if h] if mode == "single" else DUAL_SENSOR_HEADER
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to parse sensor CSV: {exc}")

    return {
        "status": "ok",
        "mode": mode,
        "header": expected_header,
        "rows": rows,
    }
