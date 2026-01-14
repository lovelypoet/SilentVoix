# live_mock_backend.py
import asyncio
import json
import random
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI()

# Allow your frontend origin
origins = [
    "http://localhost:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

GESTURES = ["Hello", "Yes", "No", "We", "Are", "Students", "Rest"]

@app.websocket("/ws/stream")
async def websocket_stream(ws: WebSocket):
    await ws.accept()
    print("Client connected")
    try:
        while True:
            prediction = random.choice(GESTURES)
            confidence = round(random.uniform(0.7, 1.0), 2)
            message = json.dumps({"prediction": prediction, "confidence": confidence})
            await ws.send_text(message)
            await asyncio.sleep(1)  # send a prediction every 1 second
    except Exception as e:
        print("WebSocket error:", e)
    finally:
        print("Client disconnected")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
