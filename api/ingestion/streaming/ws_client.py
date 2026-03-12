# backend/ingestion/streaming/ws_client.py
import asyncio
import websockets
import json
import logging

logger = logging.getLogger("ws_client")

class WSClient:
    def __init__(self, url, session_id="demo", batch_size=5, batch_interval=0.05):
        """
        url: WebSocket URL
        session_id: optional session identifier
        batch_size: max number of sequences per send
        batch_interval: time to wait before sending a batch (seconds)
        """
        self.url = url
        self.session_id = session_id
        self.batch_size = batch_size
        self.batch_interval = batch_interval
        self.queue = []
        self.ws = None
        self.connected = False

    async def connect(self):
        headers = {"Origin": "http://localhost:5173"}  # prevent 403
        while True:
            try:
                async with websockets.connect(self.url, extra_headers=headers) as ws:
                    self.ws = ws
                    self.connected = True
                    logger.info("Connected to WS backend")
                    await self._send_loop()
            except Exception as e:
                self.connected = False
                logger.warning(f"WebSocket error: {e}, reconnecting in 2s")
                await asyncio.sleep(2)

    def enqueue(self, sequence):
        """Add a gesture window to the queue."""
        self.queue.append(sequence)

    async def _send_loop(self):
        """Continuously send batches from the queue."""
        while True:
            if not self.queue:
                await asyncio.sleep(self.batch_interval)
                continue

            # Take up to batch_size sequences
            batch = self.queue[:self.batch_size]
            self.queue = self.queue[self.batch_size:]

            payload = {
                "sensor_values": batch,
                "session_id": self.session_id
            }
            try:
                await self.ws.send(json.dumps(payload))
                resp = await self.ws.recv()
                data = json.loads(resp)
                pred = data.get("prediction")
                logger.info(f"WS batch sent. Latest prediction: {pred}")
            except Exception as e:
                logger.error(f"Error sending WS batch: {e}")
                self.queue = batch + self.queue  # requeue unsent batch
                await asyncio.sleep(1)  # wait before retry
