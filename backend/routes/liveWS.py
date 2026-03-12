"""
Live sensor WebSocket route used by serial bridge (producer) and training UI (consumer).

Supported producer payloads:
- v1: {"type":"sensor_frame_v1","frame":{"flex":[5],"accel":[3],"gyro":[3]}, ...}
- legacy split: {"left":[5],"right":[3],"imu":[3], ...}
- legacy flat: {"values":[11]} or {"sensor_values":[[11], ...]}
- raw csv text: "v1,v2,...,v11"
"""

import json
import logging
import time
from typing import Any, Dict, List, Set, Tuple

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ingestion.streaming.live_data import update_data

logger = logging.getLogger("signglove")
router = APIRouter(prefix="/ws", tags=["WebSocket"])

SCHEMA_NAME = "silentvoix.sensor_frame.v1"
SCHEMA_VERSION = "1.0"
TOTAL_VALUES = 11

active_connections: Set[WebSocket] = set()
_frame_count = 0
_last_log_ts = 0.0


def _to_float_list(values: Any) -> List[float]:
    if not isinstance(values, list):
        raise ValueError("values must be a list")
    out = []
    for value in values:
        out.append(float(value))
    return out


def _from_v1(payload: Dict[str, Any]) -> Tuple[List[float], Dict[str, List[float]]]:
    frame = payload.get("frame")
    if isinstance(frame, dict):
        flex = _to_float_list(frame.get("flex", []))
        accel = _to_float_list(frame.get("accel", []))
        gyro = _to_float_list(frame.get("gyro", []))
        values = flex + accel + gyro
    elif isinstance(frame, list):
        values = _to_float_list(frame)
        flex = values[:5]
        accel = values[5:8]
        gyro = values[8:11]
    else:
        raise ValueError("v1 frame must be object or list")

    if len(values) != TOTAL_VALUES:
        raise ValueError(f"Expected {TOTAL_VALUES} values, got {len(values)}")
    if len(flex) != 5 or len(accel) != 3 or len(gyro) != 3:
        raise ValueError("frame must contain flex(5), accel(3), gyro(3)")
    # Normalize output order to imu_flex: accel + gyro + flex
    values_out = accel + gyro + flex
    return values_out, {"flex": flex, "accel": accel, "gyro": gyro}


def _normalize_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    payload_type = payload.get("type")
    session_id = payload.get("session_id")
    source = str(payload.get("source", "livews"))
    timestamp_ms_raw = payload.get("timestamp_ms")
    timestamp_ms = int(timestamp_ms_raw) if timestamp_ms_raw is not None else int(time.time() * 1000)

    if payload_type == "sensor_frame_v1":
        values, channels = _from_v1(payload)
    elif isinstance(payload.get("left"), list) and isinstance(payload.get("right"), list) and isinstance(payload.get("imu"), list):
        flex = _to_float_list(payload.get("left", []))
        accel = _to_float_list(payload.get("right", []))
        gyro = _to_float_list(payload.get("imu", []))
        values = flex + accel + gyro
        if len(values) != TOTAL_VALUES:
            raise ValueError("legacy split payload must have left(5)+right(3)+imu(3)")
        channels = {"flex": flex, "accel": accel, "gyro": gyro}
    elif isinstance(payload.get("values"), list):
        values = _to_float_list(payload["values"])
        if len(values) != TOTAL_VALUES:
            raise ValueError(f"values must have {TOTAL_VALUES} entries")
        # Treat incoming flat values as imu_flex.
        accel = values[0:3]
        gyro = values[3:6]
        flex = values[6:11]
        values = accel + gyro + flex
        channels = {"flex": flex, "accel": accel, "gyro": gyro}
    elif isinstance(payload.get("sensor_values"), list):
        sensor_values = payload["sensor_values"]
        if not sensor_values:
            raise ValueError("sensor_values must not be empty")
        latest = sensor_values[-1]
        values = _to_float_list(latest)
        if len(values) != TOTAL_VALUES:
            raise ValueError(f"sensor_values frame must have {TOTAL_VALUES} entries")
        accel = values[0:3]
        gyro = values[3:6]
        flex = values[6:11]
        values = accel + gyro + flex
        channels = {"flex": flex, "accel": accel, "gyro": gyro}
    else:
        raise ValueError("Unsupported payload shape")

    return {
        "type": "sensor_frame",
        "schema": SCHEMA_NAME,
        "schema_version": SCHEMA_VERSION,
        "session_id": session_id,
        "source": source,
        "timestamp_ms": timestamp_ms,
        "received_at_ms": int(time.time() * 1000),
        "channels": channels,
        "values": values,
    }


def _parse_text_payload(text: str) -> Dict[str, Any]:
    stripped = text.strip()
    if not stripped:
        raise ValueError("Empty payload")

    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        parts = [p.strip() for p in stripped.split(",")]
        if len(parts) != TOTAL_VALUES:
            raise ValueError("Invalid CSV frame, expected 11 comma-separated values")
        payload = {"values": [float(p) for p in parts]}

    if not isinstance(payload, dict):
        raise ValueError("Payload must be a JSON object")
    return payload


async def _broadcast_json(message: Dict[str, Any]) -> None:
    dead: List[WebSocket] = []
    for connection in active_connections:
        try:
            await connection.send_json(message)
        except Exception:
            dead.append(connection)
    for connection in dead:
        active_connections.discard(connection)


@router.websocket("/stream")
async def websocket_stream(websocket: WebSocket):
    await websocket.accept()
    active_connections.add(websocket)
    client_ip = websocket.client.host if websocket.client else "unknown"
    logger.info(f"livews connected: {client_ip} (clients={len(active_connections)})")

    await websocket.send_json(
        {
            "type": "connection_established",
            "endpoint": "/ws/stream",
            "schema": SCHEMA_NAME,
            "schema_version": SCHEMA_VERSION,
            "server_time_ms": int(time.time() * 1000),
        }
    )

    try:
        while True:
            raw_text = await websocket.receive_text()
            try:
                payload = _parse_text_payload(raw_text)
                msg_type = payload.get("type")

                # Allow non-producer clients (training UI) to keep socket alive.
                if msg_type in {"subscribe", "ping", "status"}:
                    if msg_type == "ping":
                        await websocket.send_json({"type": "pong", "server_time_ms": int(time.time() * 1000)})
                    else:
                        await websocket.send_json({"type": "ack", "subscribed": True, "clients": len(active_connections)})
                    continue

                normalized = _normalize_payload(payload)
                global _frame_count, _last_log_ts
                _frame_count += 1
                now = time.time()
                if now - _last_log_ts > 5:
                    _last_log_ts = now
                    logger.info(
                        "livews received frames=%s latest_ts=%s sample=%s",
                        _frame_count,
                        normalized.get("timestamp_ms"),
                        normalized.get("values"),
                    )
                # Keep latest sensor values for /gesture/latest polling.
                update_data(normalized["values"])
                await _broadcast_json(normalized)
            except Exception as exc:
                await websocket.send_json({"type": "error", "message": str(exc)})
    except WebSocketDisconnect:
        pass
    finally:
        active_connections.discard(websocket)
        logger.info(f"livews disconnected: {client_ip} (clients={len(active_connections)})")
