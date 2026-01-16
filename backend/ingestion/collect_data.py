# ------------------IMPORT NOTES------------------
# - pip install -r requirements.txt
# - Kết nối Arduino và mở đúng cổng serial

import serial
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
SERIAL_PORT = 'COM6'  # 👈 Change to your port (e.g., /dev/ttyUSB0)
BAUD_RATE = 115200
FLEX_SENSORS = 5
ACCEL_SENSORS = 3
GYRO_SENSORS = 3
TOTAL_SENSORS = FLEX_SENSORS + ACCEL_SENSORS + GYRO_SENSORS
LABEL = 'Students'  # 👈 Set this before collecting (rest gesture)
SESSION_ID = 'noun1'  # Use a simple, human-readable session id for this data collection
CSV_DIR = app_settings.DATA_DIR
RAW_DATA_PATH = os.path.join(CSV_DIR, 'Students.csv')
FILE_PATH = os.path.join(CSV_DIR, f"{LABEL}_{SESSION_ID}.csv")
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


def connect_arduino():
    try:
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
        time.sleep(2)
        logger.info(f"Connected to {SERIAL_PORT} successfully!")
        ser.reset_input_buffer()
        return ser
    except Exception as e:
        logger.error(f"Failed to connect to serial port: {e}")
        return None


def read_data(ser):
    try:
        line = ser.readline().decode('utf-8').strip()
        if line:
            val = line.split(',')
            if len(val) != TOTAL_SENSORS:
                return None
            try:
                val = list(map(int, val))
                logger.info(f"[SUCCESS] Read values: {val}")
                return val
            except ValueError:
                return None
    except Exception as e:
        logger.error(f"Error reading data: {e}")
    return None


def initialize_csv():
    try:
        os.makedirs(CSV_DIR, exist_ok=True)
        if not os.path.exists(RAW_DATA_PATH):
            with open(RAW_DATA_PATH, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                header = ['session_id', 'label', 'flex1', 'flex2', 'flex3', 'flex4', 'flex5', 'accel_x', 'accel_y', 'accel_z', 'gyro_x', 'gyro_y', 'gyro_z']
                writer.writerow(header)
            logger.info(f"CSV file created: {RAW_DATA_PATH}")
        return True
    except Exception as e:
        logger.error(f"Error creating CSV: {e}")
        return False


async def send_to_backend(data_queue):
    try:
        ws_url = app_settings.BACKEND_BASE_URL.replace("http://", "ws://").replace("https://", "wss://") + "/ws/predict"
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

    if not initialize_csv():
        return

    ser = connect_arduino()
    if ser is None:
        return

    data_queue = []
    loop = asyncio.get_event_loop()
    threading.Thread(target=loop.run_until_complete, args=(send_to_backend(data_queue),), daemon=True).start()

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
                    row = [SESSION_ID, LABEL] + data[:5] + data[5:8] + data[8:11]
                    writer.writerow(row)
                    csvfile.flush()

                    # Save to MongoDB
                    mongo_doc = {
                        "session_id": SESSION_ID,
                        "label": LABEL,
                        "timestamp": datetime.utcnow(),
                        "values": data
                    }
                    sensor_collection.insert_one(mongo_doc)

                    # Send to WebSocket
                    ws_payload = {
                        "left": data[:5],
                        "right": data[5:8],
                        "imu": data[8:11],
                        "timestamp": time.time()
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
