import asyncio
import json
import logging
import time
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("silentvoix-demo")

GESTURE_LABELS = [
    "Hello", "Yes", "No", "We", "Are",
    "Students", "Rest", "Thank You", "Please",
    "Help", "Water", "Food", "Emergency",
]

REAL_MODEL = None

try:
    import tflite_runtime.interpreter as tflite
    model_path = "backend/AI/gesture_model.tflite"
    interpreter = tflite.Interpreter(model_path=model_path)
    interpreter.allocate_tensors()
    REAL_MODEL = interpreter
    logger.info("Loaded TFLite model from %s", model_path)
except Exception:
    logger.info("No TFLite model found — using rule-based fallback predictor")


@dataclass
class ConnectionState:
    ws: WebSocket
    last_seen: float = 0.0
    anomaly_history: deque = field(default_factory=lambda: deque(maxlen=50))
    prediction_history: list = field(default_factory=list)
    left_z: float = 0.0
    right_z: float = 0.0


connected: dict[str, ConnectionState] = {}

app = FastAPI(title="SilentVoix Competition Demo")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def compute_z_scores(values: list[float]) -> float:
    if len(values) < 3:
        return 0.0
    arr = np.array(values)
    mean = np.mean(arr)
    std = np.std(arr) + 1e-8
    return float(np.abs((arr[-1] - mean) / std))


def predict_rule_based(sensor_data: dict) -> tuple[str, float]:
    flex_l = sensor_data.get("f1_l", 0) + sensor_data.get("f2_l", 0) + sensor_data.get("f3_l", 0) + sensor_data.get("f4_l", 0) + sensor_data.get("f5_l", 0)
    flex_r = sensor_data.get("f1_r", 0) + sensor_data.get("f2_r", 0) + sensor_data.get("f3_r", 0) + sensor_data.get("f4_r", 0) + sensor_data.get("f5_r", 0)
    flex_total = flex_l + flex_r
    acc_x = sensor_data.get("ax_l", 0) + sensor_data.get("ax_r", 0)

    if flex_total < 100:
        return "Rest", 0.95
    if flex_l > 300 and flex_r > 300:
        if abs(acc_x) > 1.0:
            return "Hello", 0.82
        return "Yes", 0.78
    if flex_l > 250 and flex_r < 150:
        return "No", 0.74
    if flex_r > 250 and flex_l < 150:
        return "We", 0.71
    if flex_total > 400:
        return "Students", 0.65
    if abs(acc_x) > 1.5:
        return "Are", 0.60

    idx = int(time.time() * 10) % len(GESTURE_LABELS)
    return GESTURE_LABELS[idx], 0.50 + (idx % 5) * 0.05


def predict(sensor_data: dict) -> tuple[str, float]:
    if REAL_MODEL is not None:
        try:
            input_details = REAL_MODEL.get_input_details()
            output_details = REAL_MODEL.get_output_details()
            features = np.array([[
                sensor_data.get(k, 0.0) for k in [
                    "ax_l", "ay_l", "az_l", "gx_l", "gy_l", "gz_l",
                    "f1_l", "f2_l", "f3_l", "f4_l", "f5_l",
                    "ax_r", "ay_r", "az_r", "gx_r", "gy_r", "gz_r",
                    "f1_r", "f2_r", "f3_r", "f4_r", "f5_r",
                ]
            ]], dtype=np.float32)
            REAL_MODEL.set_tensor(input_details[0]["index"], features)
            REAL_MODEL.invoke()
            output = REAL_MODEL.get_tensor(output_details[0]["index"])
            idx = int(np.argmax(output[0]))
            conf = float(output[0][idx])
            label = GESTURE_LABELS[idx] if idx < len(GESTURE_LABELS) else "Unknown"
            return label, conf
        except Exception as e:
            logger.warning("Model inference failed: %s — falling back", e)
    return predict_rule_based(sensor_data)


def parse_sensor_payload(data: dict) -> dict:
    payload = {}
    left_keys = ["ax_l", "ay_l", "az_l", "gx_l", "gy_l", "gz_l", "f1_l", "f2_l", "f3_l", "f4_l", "f5_l"]
    right_keys = ["ax_r", "ay_r", "az_r", "gx_r", "gy_r", "gz_r", "f1_r", "f2_r", "f3_r", "f4_r", "f5_r"]
    left_suffixes = ["ax", "ay", "az", "gx", "gy", "gz", "f1", "f2", "f3", "f4", "f5"]
    right_suffixes = ["ax", "ay", "az", "gx", "gy", "gz", "f1", "f2", "f3", "f4", "f5"]

    for key in left_keys:
        payload[key] = float(data.get(key, 0.0))
    for key in right_keys:
        payload[key] = float(data.get(key, 0.0))

    for suffix in left_suffixes:
        lk = f"l_{suffix}"
        if lk in data:
            payload[f"{suffix}_l"] = float(data[lk])

    for suffix in right_suffixes:
        rk = f"r_{suffix}"
        if rk in data:
            payload[f"{suffix}_r"] = float(data[rk])

    for suffix in left_suffixes:
        if suffix in data and f"{suffix}_l" not in payload:
            payload[f"{suffix}_l"] = float(data[suffix])

    return payload


def detect_anomaly(conn: ConnectionState, payload: dict) -> Optional[str]:
    left_vals = [payload.get(k, 0.0) for k in ["ax_l", "ay_l", "az_l", "f1_l", "f2_l", "f3_l", "f4_l", "f5_l"]]
    right_vals = [payload.get(k, 0.0) for k in ["ax_r", "ay_r", "az_r", "f1_r", "f2_r", "f3_r", "f4_r", "f5_r"]]
    l_mag = math.sqrt(sum(v * v for v in left_vals))
    r_mag = math.sqrt(sum(v * v for v in right_vals))

    conn.anomaly_history.append(l_mag + r_mag)
    if len(conn.anomaly_history) >= 10:
        z = compute_z_scores(list(conn.anomaly_history))
        if z > 3.0:
            return f"Anomaly detected (Z-score: {z:.1f}) — possible sensor dropout"

    if l_mag < 0.01 and r_mag > 5.0:
        return "LEFT glove stopped sending data"
    if r_mag < 0.01 and l_mag > 5.0:
        return "RIGHT glove stopped sending data"
    if l_mag < 0.01 and r_mag < 0.01:
        return "BOTH gloves stopped sending data"

    return None


async def handle_client(ws: WebSocket, client_id: str):
    conn = ConnectionState(ws=ws)
    connected[client_id] = conn
    logger.info("Client connected: %s", client_id)

    try:
        async for message in ws.iter_text():
            conn.last_seen = time.time()
            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                await ws.send_json({"error": "invalid JSON"})
                continue

            payload = parse_sensor_payload(data)

            anomaly = detect_anomaly(conn, payload)
            label, confidence = predict(payload)

            latency = (time.time() - conn.last_seen) * 1000

            result = {
                "gesture": label,
                "confidence": round(confidence, 4),
                "latency_ms": round(latency, 1),
                "timestamp": time.time(),
            }
            if anomaly:
                result["anomaly"] = anomaly

            conn.prediction_history.append(result)
            if len(conn.prediction_history) > 200:
                conn.prediction_history = conn.prediction_history[-200:]

            await ws.send_json(result)

    except WebSocketDisconnect:
        logger.info("Client disconnected: %s", client_id)
    except Exception as e:
        logger.error("Error handling %s: %s", client_id, e)
    finally:
        connected.pop(client_id, None)


@app.websocket("/ws/predict")
async def ws_predict(ws: WebSocket):
    await ws.accept()
    client_id = f"client_{id(ws)}_{int(time.time())}"
    await handle_client(ws, client_id)


@app.websocket("/ws/demo")
async def ws_demo(ws: WebSocket):
    await ws.accept()
    client_id = f"demo_{id(ws)}_{int(time.time())}"

    async def send_loop():
        while True:
            payload = generate_mock_data()
            payload["_mock"] = True
            label, confidence = predict(payload)
            result = {
                "gesture": label,
                "confidence": round(confidence, 4),
                "latency_ms": round(5.0 + abs(math.sin(time.time())) * 15, 1),
                "timestamp": time.time(),
                "_mock": True,
            }
            try:
                await ws.send_json(result)
            except Exception:
                break
            await asyncio.sleep(0.5 + abs(math.sin(time.time())) * 0.5)

    try:
        await send_loop()
    except WebSocketDisconnect:
        pass
    except Exception:
        pass


def generate_mock_data() -> dict:
    t = time.time()
    return {
        "ax_l": round(0.3 + math.sin(t * 2) * 0.5, 3),
        "ay_l": round(0.2 + math.cos(t * 1.7) * 0.4, 3),
        "az_l": round(9.8 + math.sin(t * 1.3) * 0.3, 3),
        "gx_l": round(0.1 + math.sin(t * 3) * 2.0, 3),
        "gy_l": round(0.1 + math.cos(t * 2.5) * 1.5, 3),
        "gz_l": round(0.1 + math.sin(t * 2.8) * 1.8, 3),
        "f1_l": round(150 + math.sin(t * 0.5) * 80, 1),
        "f2_l": round(120 + math.cos(t * 0.6) * 60, 1),
        "f3_l": round(100 + math.sin(t * 0.4) * 50, 1),
        "f4_l": round(80 + math.cos(t * 0.7) * 40, 1),
        "f5_l": round(60 + math.sin(t * 0.3) * 30, 1),
        "ax_r": round(0.3 + math.cos(t * 2.1) * 0.5, 3),
        "ay_r": round(0.2 + math.sin(t * 1.8) * 0.4, 3),
        "az_r": round(9.8 + math.cos(t * 1.4) * 0.3, 3),
        "gx_r": round(0.1 + math.cos(t * 3.1) * 2.0, 3),
        "gy_r": round(0.1 + math.sin(t * 2.6) * 1.5, 3),
        "gz_r": round(0.1 + math.cos(t * 2.9) * 1.8, 3),
        "f1_r": round(180 + math.cos(t * 0.55) * 90, 1),
        "f2_r": round(140 + math.sin(t * 0.65) * 70, 1),
        "f3_r": round(110 + math.cos(t * 0.45) * 55, 1),
        "f4_r": round(90 + math.sin(t * 0.75) * 45, 1),
        "f5_r": round(70 + math.cos(t * 0.35) * 35, 1),
    }


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "model": "tflite" if REAL_MODEL else "rule-based",
        "clients": len(connected),
    }


@app.get("/mock-payload")
async def mock_payload():
    return generate_mock_data()


@app.get("/labels")
async def labels():
    return {"labels": GESTURE_LABELS}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
