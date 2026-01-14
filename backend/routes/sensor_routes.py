"""
API routes for managing sensor data in the sign glove system.

Endpoints:
- POST /sensor-data: Insert new sensor data.
- GET /sensor-data: List all sensor data (optionally filter by label).
- PUT /sensor-data/{session_id}: Update label for a session.
- DELETE /sensor-data/{session_id}: Delete sensor data by session ID.
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from models.sensor_models import SensorData
from core.database import sensor_collection
from bson import ObjectId
from typing import List
from fastapi.encoders import jsonable_encoder
from routes.auth_routes import role_required_dep

router = APIRouter()

# Helper to convert Mongo _id to str
def convert_id(doc):
    """
    Convert MongoDB ObjectId to string for frontend compatibility.
    """
    doc["_id"] = str(doc["_id"])
    return doc

@router.post("/sensor-data")
async def create_sensor_data(data: SensorData, _user=Depends(role_required_dep("editor"))):
    """
    Insert new sensor data into the database.
    """
    try:
        result = await sensor_collection.insert_one(data.model_dump())
        return {"inserted_id": str(result.inserted_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sensor-data", response_model=List[SensorData])
@router.get("/sensor-data/", response_model=List[SensorData])
async def get_sensor_data(label: str = Query(None)):
    """
    List all sensor data, optionally filtered by label.
    """
    try:
        query = {"label": label} if label else {}
        cursor = sensor_collection.find(query)
        docs = [convert_id(doc) async for doc in cursor]
        return docs
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/sensor-data/{session_id}")
async def update_sensor_label(session_id: str, label: str = Query(...), _user=Depends(role_required_dep("editor"))):
    """
    Update the label for a specific sensor data session.
    """
    try:
        result = await sensor_collection.update_one(
            {"session_id": session_id},
            {"$set": {"label": label}}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"message": "Label updated", "modified_count": result.modified_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/sensor-data/{session_id}")
async def delete_sensor_data(session_id: str, _user=Depends(role_required_dep("editor"))):
    """
    Delete sensor data for a specific session by session ID.
    """
    try:
        result = await sensor_collection.delete_one({"session_id": session_id})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Session not found")
        return {"message": "Sensor data deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
