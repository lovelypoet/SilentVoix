"""
API route for receiving and storing sensor data from the glove device (offline/local mode).

Endpoint:
- POST /data: Receive and store sensor data with a server-side timestamp.
"""
# routes/data.py

from fastapi import APIRouter, HTTPException
from db.mongo import get_sensor_collection
from models.sensor_models import SensorData
from datetime import datetime, timezone

router = APIRouter()
collection = get_sensor_collection()

@router.post("/data")
async def receive_data(data: SensorData):
    """
    Receive sensor data and store it in the local database with a server-side timestamp.
    """
    try:
        # Add server-side timestamp (optional, to override or ensure consistency)
        doc = data.dict()
        doc["_timestamp"] = datetime.now(timezone.utc)

        result = await collection.insert_one(doc)
        return {"status": "success", "inserted_id": str(result.inserted_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
