import time
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ingestion.sync_stream import SyncStreamBuffer, load_sensor_series

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
                    buffer.add_cv_sample(float(velocity))

            now = time.time()
            if msg_type == "tick" or (now - last_send) >= 0.1:
                sensor_series = load_sensor_series(mode=mode, limit=200, max_points=60)
                sensor_stats = buffer.compute_sensor_stats(sensor_series)
                cv_series = buffer.get_cv_series()
                cv_stats = buffer.compute_cv_stats(cv_series)
                payload = {
                    "type": "sync_series",
                    "mode": mode,
                    "sensor": {
                        "series": sensor_series,
                        "threshold": sensor_stats["threshold"],
                        "spike_index": sensor_stats["spike_index"],
                        "spike_active": sensor_stats["spike_active"],
                    },
                    "cv": {
                        "series": cv_series,
                        "threshold": cv_stats["threshold"],
                        "spike_index": cv_stats["spike_index"],
                        "spike_active": cv_stats["spike_active"],
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
