import time
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ingestion.sync_stream import SyncStreamBuffer, load_sensor_samples

ws_router = APIRouter(prefix="/ws", tags=["WebSocket"])
http_router = APIRouter(prefix="/sync", tags=["Sync"])

_last_payload = None
_last_update = 0.0
_payload_lock = asyncio.Lock()


@ws_router.websocket("/sync")
async def websocket_sync_stream(websocket: WebSocket):
    await websocket.accept()
    buffer = SyncStreamBuffer(max_points=60)
    mode = "single"
    simulate = False
    last_send = 0.0

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "cv_sample")

            if msg_type == "configure":
                mode = data.get("mode", mode)
                if mode not in ["single", "dual"]:
                    mode = "single"
                simulate = bool(data.get("simulate", simulate))
                await websocket.send_json({"type": "ack", "mode": mode, "simulate": simulate})
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
                sensor_samples = load_sensor_samples(mode=mode, limit=200, max_points=60, simulate=simulate)
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
