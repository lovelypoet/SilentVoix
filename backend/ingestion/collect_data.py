# ------------------IMPORT NOTES------------------
# - pip install -r requirements.txt
# - Kết nối Arduino và mở đúng cổng serial

import serial
from serial.tools import list_ports
import time
import csv
import os
import logging
import sys
import uuid
import asyncio
import threading
import websockets
import json
import requests
from datetime import datetime
# Backend imports
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

# Keep current working directory as well
if '.' not in sys.path:
    sys.path.append('.')

from core.database import sensor_collection  # MongoDB collection
from core.settings import settings as app_settings

# ========= CONFIG =========
# Read serial port from backend settings/env to avoid hardcoded Windows COM defaults.
SERIAL_PORT = app_settings.SERIAL_PORT_SINGLE
BAUD_RATE = 115200
MAX_SAMPLES = int(os.getenv("SENSOR_CAPTURE_MAX_SAMPLES", "0") or "0")
FLEX_SENSORS = 5
ACCEL_SENSORS = 3
GYRO_SENSORS = 3
TOTAL_SENSORS = FLEX_SENSORS + ACCEL_SENSORS + GYRO_SENSORS
LABEL = 'Students'  # 👈 Set this before collecting (rest gesture)
CSV_DIR = app_settings.DATA_DIR
RAW_DATA_PATH = os.path.join(CSV_DIR, 'Students.csv')
LOG_FILE = 'data_collection.log'

# ========= Logging setup =========
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def _detected_serial_ports():
    """Return detected serial ports, prioritizing ACM/USB devices."""
    ports = [p.device for p in list_ports.comports()]
    if not ports:
        return []
    preferred = [p for p in ports if "ttyACM" in p or "ttyUSB" in p]
    remaining = [p for p in ports if p not in preferred]
    return preferred + remaining


def connect_arduino():
    candidates = []
    if SERIAL_PORT:
        candidates.append(SERIAL_PORT)
    for detected in _detected_serial_ports():
        if detected not in candidates:
            candidates.append(detected)

    if not candidates:
        logger.error("No serial ports detected.")
        return None

    for port in candidates:
        try:
            ser = serial.Serial(port, BAUD_RATE, timeout=1)
            time.sleep(2)
            logger.info(f"Connected to {port} successfully!")
            ser.reset_input_buffer()
            return ser
        except Exception as e:
            logger.warning(f"Failed to connect to serial port {port}: {e}")

    logger.error(f"Failed to connect to any serial port. Candidates tried: {candidates}")
    return None


def read_data(ser):
    try:
        line = ser.readline().decode('utf-8').strip()
        if line:
            parts = [p.strip() for p in line.split(',') if p.strip() != ""]
            try:
                values = [float(v) for v in parts]

                # Format A: 11 direct channels.
                # We accept either:
                # - flex5 + accel3 + gyro3 (legacy)
                # - accel3 + gyro3 + flex5 (ESP firmware in backend/hardware/esp.c++)
                if len(values) == TOTAL_SENSORS:
                    imu_first = values[:6]
                    flex_last = values[6:]
                    # Heuristic: IMU usually includes negatives/small magnitudes; flex_norm is often 0..1.
                    if any(v < -0.2 for v in imu_first) and all(0 <= v <= 1.2 for v in flex_last):
                        values = flex_last + imu_first[:3] + imu_first[3:6]
                # Format B: timestamp + 11 channels from ESP firmware.
                # Expected ESP order: timestamp, ax, ay, az, gx, gy, gz, f1, f2, f3, f4, f5
                elif len(values) == TOTAL_SENSORS + 1:
                    payload = values[1:]
                    imu = payload[:6]
                    flex = payload[6:]
                    if len(imu) == 6 and len(flex) == 5:
                        values = flex + imu[:3] + imu[3:6]
                    else:
                        return None
                # Format C: timestamp + accel3 + gyro3 (no flex in firmware output)
                # Example: millis, ax, ay, az, gx, gy, gz
                elif len(values) == 7:
                    imu = values[1:]
                    values = [0.0, 0.0, 0.0, 0.0, 0.0] + imu
                else:
                    return None

                logger.info(f"[SUCCESS] Read values: {values}")
                return values
            except ValueError:
                return None
    except Exception as e:
        logger.error(f"Error reading data: {e}")
    return None


def initialize_csv():
    expected_header = [
        'timestamp_ms',
        'ax', 'ay', 'az',
        'gx', 'gy', 'gz',
        'f1', 'f2', 'f3', 'f4', 'f5',
        'label',
    ]
    try:
        os.makedirs(CSV_DIR, exist_ok=True)
        if os.path.exists(RAW_DATA_PATH):
            with open(RAW_DATA_PATH, 'r', encoding='utf-8', errors='ignore', newline='') as csvfile:
                reader = csv.reader(csvfile)
                first_row = next(reader, [])
            if first_row and first_row != expected_header:
                stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                archived_path = os.path.join(CSV_DIR, f"Students_legacy_schema_{stamp}.csv")
                os.rename(RAW_DATA_PATH, archived_path)
                logger.warning(
                    "Detected legacy Students.csv schema. "
                    f"Archived old file to {archived_path} and creating a new aligned file."
                )

        if not os.path.exists(RAW_DATA_PATH):
            with open(RAW_DATA_PATH, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(expected_header)
            logger.info(f"CSV file created: {RAW_DATA_PATH}")
        return True
    except Exception as e:
        logger.error(f"Error creating CSV: {e}")
        return False


async def send_to_backend(data_queue):
    try:
        ws_url = app_settings.BACKEND_BASE_URL.replace("http://", "ws://").replace("https://", "wss://") + "/ws/stream"
        async with websockets.connect(ws_url) as ws:
            logger.info(f"WebSocket connected to {ws_url}.")
            while True:
                if not data_queue:
                    await asyncio.sleep(0.05)
                    continue
                data = data_queue.pop(0)
                await ws.send(json.dumps(data))
    except Exception as e:
        logger.error(f"WebSocket error: {e}")


def main():
    print("=============== Starting Data Collection ===============")
    logger.info(f"Writing CSV to: {os.path.abspath(RAW_DATA_PATH)}")
    if MAX_SAMPLES > 0:
        logger.info(f"Max samples configured: {MAX_SAMPLES}")

    if not initialize_csv():
        return

    ser = connect_arduino()
    if ser is None:
        return

    data_queue = []
    # Run the async websocket forwarder on its own thread/event loop.
    threading.Thread(target=lambda: asyncio.run(send_to_backend(data_queue)), daemon=True).start()

    try:
        with open(RAW_DATA_PATH, 'a', newline='') as csvfile:
            writer = csv.writer(csvfile)
            log = 0
            row_count = 0
            milestones = {10, 50, 100, 1000, 2000}
            printed_milestones = set()

            while True:
                data = read_data(ser)
                if data:
                    timestamp_ms = int(time.time() * 1000)
                    # `data` is internal order: flex(5) + accel(3) + gyro(3).
                    # Write CSV in ESP-aligned order: timestamp, accel, gyro, flex, label.
                    row = [timestamp_ms] + data[5:8] + data[8:11] + data[:5] + [LABEL]
                    writer.writerow(row)
                    csvfile.flush()

                    # Save to MongoDB
                    mongo_doc = {
                        "session_id": "auto_single",
                        "label": LABEL,
                        "timestamp": datetime.utcnow(),
                        "timestamp_ms": timestamp_ms,
                        "values": data
                    }
                    sensor_collection.insert_one(mongo_doc)

                    # Send to WebSocket
                    ws_payload = {
                        "type": "sensor_frame_v1",
                        "schema_version": "1.0",
                        "session_id": "auto_single",
                        "source": "pyserial.collect_data",
                        "timestamp_ms": timestamp_ms,
                        "frame": {
                            "flex": data[:5],
                            "accel": data[5:8],
                            "gyro": data[8:11],
                        },
                    }
                    data_queue.append(ws_payload)

                    log += 1
                    row_count += 1
                    if row_count in milestones and row_count not in printed_milestones:
                        print(f"Live row count: {row_count}")
                        printed_milestones.add(row_count)
                    if row_count == 2000:
                        print("You have reached 2000 rows. Please stop data collection and proceed to noise reduction.")
                        milestones.clear()
                    if MAX_SAMPLES > 0 and row_count >= MAX_SAMPLES:
                        logger.info(f"Reached max sample limit ({MAX_SAMPLES}). Stopping capture loop.")
                        break

                time.sleep(0.001)

    except PermissionError:
        logger.error(f"Permission denied for {RAW_DATA_PATH}")
    except KeyboardInterrupt:
        logger.info("Stopped by user.")
        try:
            logger.info("Triggering model training...")
            # Include internal API key to bypass auth
            response = requests.post(
                f"{app_settings.BACKEND_BASE_URL}/training/trigger",
                headers={"X-API-KEY": app_settings.SECRET_KEY}
            )
            if response.status_code == 200:
                logger.info("Training triggered successfully.")
            else:
                logger.error(f"Training trigger failed: {response.status_code} - {response.text}")
        except Exception as e:
            logger.error(f"Error triggering training: {e}")
    finally:
        if ser and ser.is_open:
            ser.close()
            logger.info("Serial connection closed.")
        # Print number of rows in raw_data.csv
        try:
            with open(RAW_DATA_PATH, 'r', newline='') as f:
                row_count = sum(1 for _ in f) - 1  # exclude header
            print(f"Total rows in raw_data.csv: {row_count}")
        except Exception as e:
            print(f"Could not count rows in raw_data.csv: {e}")

        # Count and print label distribution for raw_data.csv
        try:
            from collections import Counter
            label_counts = Counter()
            with open(RAW_DATA_PATH, 'r', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    label = row["label"]
                    label_counts[label] += 1
            print("Label distribution in raw_data.csv:")
            for label, count in label_counts.items():
                print(f"  {label}: {count}")
        except Exception as e:
            print(f"Could not count label distribution: {e}")

        # Count and print label distribution for gesture_data.csv if it exists
        GESTURE_DATA_PATH = f"{CSV_DIR}/gesture_data.csv"
        if os.path.exists(GESTURE_DATA_PATH):
            try:
                label_counts = Counter()
                with open(GESTURE_DATA_PATH, 'r', newline='') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        label = row["label"]
                        label_counts[label] += 1
                print("Label distribution in gesture_data.csv:")
                for label, count in label_counts.items():
                    print(f"  {label}: {count}")
            except Exception as e:
                print(f"Could not count label distribution in gesture_data.csv: {e}")


if __name__ == "__main__":
    main()
