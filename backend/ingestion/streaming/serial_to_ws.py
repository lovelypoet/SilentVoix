import argparse
import asyncio
import json
import logging
import time
from typing import List, Optional, Tuple

import serial
import websockets


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("serial_to_ws")

ORDER_IMU_FLEX = "imu_flex"   # ax, ay, az, gx, gy, gz, f1..f5
ORDER_FLEX_IMU = "flex_imu"   # f1..f5, ax, ay, az, gx, gy, gz


def parse_line(line: str) -> Optional[Tuple[List[float], Optional[int]]]:
    stripped = line.strip()
    if not stripped:
        return None
    if any(token in stripped.lower() for token in ("calibrating", "ready", "sensor connected", "error")):
        return None
    parts = [p.strip() for p in stripped.split(",") if p.strip()]
    try:
        values = [float(p) for p in parts]
    except ValueError:
        return None
    if len(values) == 12:
        ts = int(values[0])
        return values[1:], ts
    if len(values) == 11:
        return values, None
    return None


def build_v1_frame(values: List[float], order: str) -> Optional[dict]:
    if len(values) != 11:
        return None
    if order == ORDER_IMU_FLEX:
        accel = values[0:3]
        gyro = values[3:6]
        flex = values[6:11]
    elif order == ORDER_FLEX_IMU:
        flex = values[0:5]
        accel = values[5:8]
        gyro = values[8:11]
    else:
        return None
    return {"flex": flex, "accel": accel, "gyro": gyro}


async def stream_serial(
    port: str,
    baud: int,
    ws_url: str,
    order: str,
    session_id: str,
    log_every: int,
    debug_raw: bool,
) -> None:
    while True:
        ser = None
        try:
            ser = serial.Serial(port, baud, timeout=0.2)
            time.sleep(2)
            ser.reset_input_buffer()
            logger.info("Serial connected on %s", port)
        except Exception as exc:
            logger.error("Serial connect failed: %s", exc)
            await asyncio.sleep(2)
            continue

        try:
            async with websockets.connect(ws_url, ping_interval=20, ping_timeout=20) as ws:
                logger.info("WebSocket connected: %s", ws_url)
                sent = 0
                while True:
                    try:
                        raw = ser.readline().decode("utf-8", errors="ignore")
                    except Exception as exc:
                        logger.error("Serial read error: %s", exc)
                        break

                    if debug_raw and raw.strip():
                        logger.info("RAW: %s", raw.strip())

                    parsed = parse_line(raw)
                    if not parsed:
                        await asyncio.sleep(0.001)
                        continue

                    values, ts = parsed
                    frame = build_v1_frame(values, order)
                    if not frame:
                        continue

                    payload = {
                        "type": "sensor_frame_v1",
                        "frame": frame,
                        "session_id": session_id,
                        "source": "serial_to_ws",
                    }
                    if ts is not None:
                        payload["timestamp_ms"] = ts

                    try:
                        await ws.send(json.dumps(payload))
                        sent += 1
                        if log_every and sent % log_every == 0:
                            logger.info("Sent %d frames (latest ts=%s)", sent, ts if ts is not None else "n/a")
                    except Exception as exc:
                        logger.error("WebSocket send error: %s", exc)
                        break
        except Exception as exc:
            logger.warning("WebSocket error: %s", exc)
        finally:
            try:
                if ser and ser.is_open:
                    ser.close()
            except Exception:
                pass
            await asyncio.sleep(2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Stream ESP32 serial frames to /ws/stream.")
    parser.add_argument("--port", default="/dev/ttyACM0")
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--ws-url", default="ws://127.0.0.1:8000/ws/stream")
    parser.add_argument("--order", choices=[ORDER_IMU_FLEX, ORDER_FLEX_IMU], default=ORDER_IMU_FLEX)
    parser.add_argument("--session-id", default="serial")
    parser.add_argument("--log-every", type=int, default=50, help="Log every N frames sent (0 to disable).")
    parser.add_argument("--debug-raw", action="store_true", help="Log raw serial lines.")
    args = parser.parse_args()

    logger.info(
        "Starting serial_to_ws (port=%s baud=%s ws=%s order=%s session=%s)",
        args.port,
        args.baud,
        args.ws_url,
        args.order,
        args.session_id,
    )
    asyncio.run(stream_serial(
        args.port,
        args.baud,
        args.ws_url,
        args.order,
        args.session_id,
        args.log_every,
        args.debug_raw,
    ))


if __name__ == "__main__":
    main()
