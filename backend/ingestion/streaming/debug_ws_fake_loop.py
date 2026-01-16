import asyncio
import json
import websockets
import time

async def handler(ws):
    print("Client connected")
    try:
        while True:
            payload = {"gesture": "Test", "confidence": 1.0, "timestamp": int(time.time()*1000)}
            await ws.send(json.dumps(payload))
            await asyncio.sleep(0.5)
    except websockets.exceptions.ConnectionClosed:
        print("Client disconnected")

async def main():
    server = await websockets.serve(handler, "127.0.0.1", 8765)
    print("Debug WS server running at ws://127.0.0.1:8765")
    await server.wait_closed()

asyncio.run(main())
