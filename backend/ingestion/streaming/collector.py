# backend/ingestion/streaming/collector.py
import asyncio
import logging
import json
from serial_reader import SerialReader
from preprocessing import normalize_sensor_data
from config_loader import load_config
from movement_detection import MovementDetector
import websockets

# Logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("collector")

# WebSocket sender config
USE_WS = True
BATCH_SIZE = 5
BATCH_DELAY = 0.05  # seconds
EXPECTED_VALUES = 11  # must match model input

async def ws_sender(ws_url, sequence_queue, session_id="demo", batch_size=BATCH_SIZE):
    """Send frames individually via WebSocket with slight delay."""
    while True:
        try:
            async with websockets.connect(ws_url) as ws:
                logger.info("Connected to WS backend")

                while True:
                    try:
                        # Wait for next batch from queue
                        seq = await asyncio.wait_for(sequence_queue.get(), timeout=BATCH_DELAY)
                        # seq is a list of frames
                        for frame in seq:
                            payload = {"sensor_values": [frame], "session_id": session_id}
                            await ws.send(json.dumps(payload))
                            logger.info(f"Sent 1 frame: {frame}")
                            await asyncio.sleep(0.5)  # ~30ms delay between frames

                    except asyncio.TimeoutError:
                        pass  # nothing to send yet

        except Exception as e:
            logger.warning(f"WebSocket error: {e}, reconnecting in 2s")
            await asyncio.sleep(2)

async def read_serial_loop(reader, detector, sequence_queue):
    """Read real sensor data, normalize, detect gestures, and queue for sending."""

    while True:
        raw_values = reader.read()  # must return 11 float values per frame
        if raw_values:
            try:
                frame = [float(v) for v in raw_values]
            except Exception as e:
                logger.warning(f"Invalid frame skipped: {raw_values} ({e})")
                await asyncio.sleep(0.01)
                continue

            # Pad or truncate to exactly 11 values
            if len(frame) < EXPECTED_VALUES:
                frame += [0.0] * (EXPECTED_VALUES - len(frame))
            elif len(frame) > EXPECTED_VALUES:
                frame = frame[:EXPECTED_VALUES]

            normalized = normalize_sensor_data(frame)
            gesture_window = detector.update(normalized)

            if gesture_window:
                # Ensure every frame has exactly 11 values
                clean_window = [
                    (f + [0.0]*(EXPECTED_VALUES - len(f)))[:EXPECTED_VALUES]
                    for f in gesture_window
                ]
                if USE_WS:
                    await sequence_queue.put(clean_window)
                    logger.info(f"Queued batch of {len(clean_window)} frames")

        await asyncio.sleep(0.01)

async def main():
    cfg = load_config()
    serial_cfg = cfg["serial"]
    backend_cfg = cfg["backend"]

    reader = SerialReader(
        port=serial_cfg["port"],
        baud_rate=serial_cfg["baud_rate"],
        total_sensors=serial_cfg["total_sensors"],
        reconnect_delay=serial_cfg["reconnect_delay"]
    )
    reader.connect()

    detector = MovementDetector(
        threshold=0.01,
        window_size=5,
        min_length=10
    )

    sequence_queue = asyncio.Queue(maxsize=100)

    if USE_WS:
        asyncio.create_task(ws_sender(backend_cfg["ws_url"], sequence_queue, backend_cfg["session_id"]))

    try:
        await read_serial_loop(reader, detector, sequence_queue)
    except KeyboardInterrupt:
        logger.info("Stopped by user")
    finally:
        reader.close()
        logger.info("Collector closed")

if __name__ == "__main__":
    asyncio.run(main())
