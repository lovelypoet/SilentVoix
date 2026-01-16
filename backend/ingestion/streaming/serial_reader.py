# backend/ingestion/streaming/serial_reader.py
import serial
import time
import logging

logger = logging.getLogger("serial_reader")

class SerialReader:
    def __init__(self, port="COM6", baud_rate=115200, total_sensors=11,reconnect_delay=1.0):
        self.port = port
        self.baud_rate = baud_rate
        self.total_sensors = total_sensors
        self.reconnect_delay = reconnect_delay
        self.ser = None

    def connect(self):
        try:
            self.ser = serial.Serial(self.port, self.baud_rate, timeout=1)
            time.sleep(2)  # allow ESP32 reset
            self.ser.reset_input_buffer()
            logger.info(f"Connected to Arduino on {self.port}")
        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            self.ser = None

    def read(self):
        """Read one line of sensor data and return list of floats."""
        if not self.ser or not self.ser.is_open:
            return None
        try:
            line = self.ser.readline().decode("utf-8").strip()
            if not line:
                return None
            vals = [float(x) for x in line.split(",")]
            if len(vals) != self.total_sensors:
                return None
            return vals
        except Exception as e:
            logger.error(f"Read error: {e}")
            return None

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()
            logger.info("Serial connection closed.")
