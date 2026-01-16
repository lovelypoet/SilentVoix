# ------------------DUAL HAND DATA COLLECTION------------------
# - pip install -r requirements.txt
# - Connect both Arduino gloves to different serial ports
# - This script collects data from both hands simultaneously

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
from typing import Dict, List, Optional, Tuple

# Backend imports
backend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

from core.database import sensor_collection
from core.settings import settings as app_settings

# ========= DUAL HAND CONFIG =========
LEFT_HAND_PORT = 'COM5'   # 👈 Change to your left hand port
RIGHT_HAND_PORT = 'COM6'  # 👈 Change to your right hand port
BAUD_RATE = 115200

# Sensor configuration per hand
FLEX_SENSORS_PER_HAND = 5
ACCEL_SENSORS_PER_HAND = 3
GYRO_SENSORS_PER_HAND = 3
SENSORS_PER_HAND = FLEX_SENSORS_PER_HAND + ACCEL_SENSORS_PER_HAND + GYRO_SENSORS_PER_HAND
TOTAL_SENSORS = SENSORS_PER_HAND * 2  # 22 total sensors

LABEL = 'Hello'  # 👈 Set this before collecting (gesture label)
SESSION_ID = 'dual_g1'  # Session ID for dual-hand data
CSV_DIR = app_settings.DATA_DIR
RAW_DATA_PATH = os.path.join(CSV_DIR, 'dual_hand_raw_data.csv')
LOG_FILE = 'dual_hand_data_collection.log'

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

class DualHandDataCollector:
    def __init__(self):
        self.left_serial = None
        self.right_serial = None
        self.data_queue = []
        
    def connect_arduinos(self) -> bool:
        """Connect to both Arduino devices"""
        try:
            # Connect to left hand
            self.left_serial = serial.Serial(LEFT_HAND_PORT, BAUD_RATE, timeout=1)
            time.sleep(2)
            self.left_serial.reset_input_buffer()
            logger.info(f"Connected to left hand on {LEFT_HAND_PORT}")
            
            # Connect to right hand
            self.right_serial = serial.Serial(RIGHT_HAND_PORT, BAUD_RATE, timeout=1)
            time.sleep(2)
            self.right_serial.reset_input_buffer()
            logger.info(f"Connected to right hand on {RIGHT_HAND_PORT}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to Arduino(s): {e}")
            return False
    
    def read_hand_data(self, ser: serial.Serial, hand_name: str) -> Optional[List[int]]:
        """Read sensor data from one hand"""
        try:
            if ser.in_waiting > 0:
                line = ser.readline().decode('utf-8').strip()
                if line:
                    # Parse CSV format: flex1,flex2,flex3,flex4,flex5,accX,accY,accZ,gyroX,gyroY,gyroZ
                    values = [int(x) for x in line.split(',') if x.strip()]
                    if len(values) == SENSORS_PER_HAND:
                        logger.debug(f"{hand_name} hand data: {values}")
                        return values
                    else:
                        logger.warning(f"{hand_name} hand: Expected {SENSORS_PER_HAND} values, got {len(values)}")
            return None
        except Exception as e:
            logger.error(f"Error reading {hand_name} hand data: {e}")
            return None
    
    def read_dual_hand_data(self) -> Optional[Dict]:
        """Read data from both hands simultaneously"""
        left_data = self.read_hand_data(self.left_serial, "Left")
        right_data = self.read_hand_data(self.right_serial, "Right")
        
        if left_data and right_data:
            return {
                "left": left_data,
                "right": right_data,
                "timestamp": time.time(),
                "session_id": SESSION_ID,
                "label": LABEL
            }
        return None
    
    def save_to_csv(self, data: Dict):
        """Save dual-hand data to CSV"""
        try:
            # Create header if file doesn't exist
            file_exists = os.path.exists(RAW_DATA_PATH)
            
            with open(RAW_DATA_PATH, 'a', newline='') as csvfile:
                writer = csv.writer(csvfile)
                
                # Write header if new file
                if not file_exists:
                    header = ['session_id', 'label', 'timestamp']
                    # Left hand sensors
                    for i in range(FLEX_SENSORS_PER_HAND):
                        header.append(f'left_flex_{i+1}')
                    for i in range(ACCEL_SENSORS_PER_HAND):
                        header.append(f'left_acc_{i+1}')
                    for i in range(GYRO_SENSORS_PER_HAND):
                        header.append(f'left_gyro_{i+1}')
                    # Right hand sensors
                    for i in range(FLEX_SENSORS_PER_HAND):
                        header.append(f'right_flex_{i+1}')
                    for i in range(ACCEL_SENSORS_PER_HAND):
                        header.append(f'right_acc_{i+1}')
                    for i in range(GYRO_SENSORS_PER_HAND):
                        header.append(f'right_gyro_{i+1}')
                    writer.writerow(header)
                
                # Write data row
                row = [data['session_id'], data['label'], data['timestamp']]
                row.extend(data['left'])  # 11 left hand values
                row.extend(data['right']) # 11 right hand values
                writer.writerow(row)
                csvfile.flush()
                
        except Exception as e:
            logger.error(f"Error saving to CSV: {e}")
    
    def save_to_mongodb(self, data: Dict):
        """Save dual-hand data to MongoDB"""
        try:
            mongo_doc = {
                "session_id": data['session_id'],
                "label": data['label'],
                "timestamp": datetime.utcnow(),
                "left_hand": data['left'],
                "right_hand": data['right'],
                "combined_values": data['left'] + data['right'],  # 22 total values
                "source": "dual_hand_collection"
            }
            sensor_collection.insert_one(mongo_doc)
            logger.debug("Data saved to MongoDB")
            
        except Exception as e:
            logger.error(f"Error saving to MongoDB: {e}")
    
    async def send_to_websocket(self, data: Dict):
        """Send data to WebSocket for real-time processing"""
        try:
            async with websockets.connect('ws://localhost:8000/ws/predict') as websocket:
                ws_payload = {
                    "left": data['left'],
                    "right": data['right'],
                    "timestamp": data['timestamp']
                }
                await websocket.send(json.dumps(ws_payload))
                logger.debug("Data sent to WebSocket")
                
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
    
    def run_collection(self):
        """Main data collection loop"""
        print("=============== Starting Dual-Hand Data Collection ===============")
        logger.info(f"Writing CSV to: {os.path.abspath(RAW_DATA_PATH)}")
        
        if not self.connect_arduinos():
            return
        
        try:
            row_count = 0
            milestones = {10, 50, 100, 500, 1000, 2000}
            printed_milestones = set()
            
            print(f"Collecting data for gesture: {LABEL}")
            print("Press Ctrl+C to stop collection")
            
            while True:
                data = self.read_dual_hand_data()
                
                if data:
                    # Save to CSV
                    self.save_to_csv(data)
                    
                    # Save to MongoDB
                    self.save_to_mongodb(data)
                    
                    # Add to WebSocket queue
                    self.data_queue.append(data)
                    
                    row_count += 1
                    
                    # Print milestones
                    if row_count in milestones and row_count not in printed_milestones:
                        print(f"Collected {row_count} dual-hand samples")
                        printed_milestones.add(row_count)
                    
                    if row_count == 2000:
                        print("You have reached 2000 samples. Please stop data collection.")
                        break
                
                time.sleep(0.1)  # 10 Hz sampling rate
                
        except KeyboardInterrupt:
            print("\nStopped by user.")
            self.trigger_training()
        finally:
            self.cleanup()
    
    def trigger_training(self):
        """Trigger model training after data collection"""
        try:
            logger.info("Triggering dual-hand model training...")
            response = requests.post(
                f"{app_settings.BACKEND_BASE_URL}/training/trigger",
                headers={"X-API-KEY": app_settings.SECRET_KEY}
            )
            if response.status_code == 200:
                logger.info("Training triggered successfully.")
            else:
                logger.error(f"Training trigger failed: {response.status_code}")
        except Exception as e:
            logger.error(f"Error triggering training: {e}")
    
    def cleanup(self):
        """Clean up resources"""
        if self.left_serial and self.left_serial.is_open:
            self.left_serial.close()
            logger.info("Left hand serial connection closed.")
        
        if self.right_serial and self.right_serial.is_open:
            self.right_serial.close()
            logger.info("Right hand serial connection closed.")
        
        # Print final statistics
        try:
            with open(RAW_DATA_PATH, 'r', newline='') as f:
                row_count = sum(1 for _ in f) - 1  # exclude header
            print(f"Total dual-hand samples collected: {row_count}")
        except Exception as e:
            print(f"Could not count samples: {e}")

def main():
    collector = DualHandDataCollector()
    collector.run_collection()

if __name__ == "__main__":
    main() 