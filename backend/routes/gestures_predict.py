"""
API routes for managing gesture sensor data in the sign glove system.

Endpoints:
- GET /export: Export all gesture data as CSV.
- POST /upload: Upload raw sensor data CSV file.
- GET /gestures: List all gesture sessions.
- GET /gestures/{session_id}: Get data for a specific session.
- POST /: Insert new sensor data.
- PUT /{session_id}: Update gesture label for a session.
- DELETE /{session_id}: Delete session data.
"""
from fastapi import APIRouter, HTTPException, Request, Depends, UploadFile, File
from fastapi.responses import StreamingResponse
from models.sensor_models import SensorData
from core.database import sensor_collection
from datetime import datetime, timezone
import logging
import csv
import io
import pandas as pd
from utils.cache import cacheable, get_or_set_cache
from typing import List, Dict, Any
from routes.auth_routes import role_required_dep

logger = logging.getLogger("signglove")

router = APIRouter(prefix="/gestures", tags=["Gestures"])

def get_trace_id(request: Request):
    return request.headers.get("x-trace-id", "none")

@router.get(
    "/export",
    summary="Export all gesture data as CSV",
    description="Download all gesture data in CSV format for analysis or backup."
)
async def export_gestures(request: Request):
    """
    Returns a CSV file with all gesture data.
    Example: flexSensor1,flexSensor2,...,label,source,timestamp
    """
    def fetch_csv():
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([f"flexSensor{i+1}" for i in range(11)] + ["label", "source", "timestamp"])
        return output.getvalue()
    cached_csv = get_or_set_cache("gestures_export_csv", lambda: None, ttl=30)
    if cached_csv:
        logger.info(f"[trace={get_trace_id(request)}] Served cached gesture export CSV.")
        output = io.StringIO(cached_csv)
        return StreamingResponse(output, media_type="text/csv", headers={
            "Content-Disposition": "attachment; filename=gesture_data.csv"
        })
    cursor = sensor_collection.find({}, {"_id": 0})
    rows = [doc async for doc in cursor]
    if not rows:
        logger.warning(f"[trace={get_trace_id(request)}] No gesture data found for export.")
        raise HTTPException(status_code=404, detail="No gesture data found")
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([f"flexSensor{i+1}" for i in range(11)] + ["label", "source", "timestamp"])
    for row in rows:
        values = row.get("values", [])
        label = row.get("label", "")
        source = row.get("source", "")
        ts = row.get("timestamp", "")
        writer.writerow(values + [label, source, ts])
    output.seek(0)
    logger.info(f"[trace={get_trace_id(request)}] Exported {len(rows)} gesture rows.")
    from utils.cache import cache
    cache.set("gestures_export_csv", output.getvalue(), 30)
    return StreamingResponse(output, media_type="text/csv", headers={
        "Content-Disposition": "attachment; filename=gesture_data.csv"
    })

@router.get(
    "",
    summary="List all gesture sessions",
    description="Returns a list of all gesture sessions with session_id and gesture_label."
)
@router.get(
    "/",
    summary="List all gesture sessions (alias with trailing slash)",
    description="Returns a list of all gesture sessions with session_id and gesture_label."
)
@cacheable(ttl=30)
async def list_gestures(request: Request) -> Dict[str, Any]:
    """
    Example response:
    {
        "status": "success",
        "data": [
            {"session_id": "abc123", "gesture_label": "hello"},
            ...
        ],
        "message": "All gestures retrieved"
    }
    """
    trace_id = get_trace_id(request)
    cursor = sensor_collection.find({}, {"_id": 0, "session_id": 1, "gesture_label": 1})
    gestures = await cursor.to_list(length=1000)
    logger.info(f"[trace={trace_id}] Listed {len(gestures)} gestures.")
    return {
        "status": "success",
        "data": gestures,
        "message": "All gestures retrieved"
    }

@router.get(
    "/{session_id}",
    summary="Get sensor data for a session",
    description="Fetch all sensor data for a specific session by session_id."
)
@cacheable(ttl=30)
async def get_sensor_data(session_id: str, request: Request) -> Dict[str, Any]:
    """
    Example response:
    {
        "status": "success",
        "data": { ... },
        "message": "Session data retrieved"
    }
    """
    trace_id = get_trace_id(request)
    data = await sensor_collection.find_one({"session_id": session_id})
    if not data:
        logger.warning(f"[trace={trace_id}] Session not found: {session_id}")
        raise HTTPException(status_code=404, detail="Session not found")
    data["_id"] = str(data["_id"])
    logger.info(f"[trace={trace_id}] Retrieved session: {session_id}")
    return {
        "status": "success",
        "data": data,
        "message": "Session data retrieved"
    }

@router.post(
    "",
    summary="Insert new sensor data",
    description="Insert a new batch of sensor data into the database."
)
async def create_sensor_data(data: SensorData, request: Request, _user=Depends(role_required_dep("editor"))) -> Dict[str, Any]:
    """
    Example response:
    {
        "status": "success",
        "data": {"inserted_id": "..."},
        "message": "Sensor data inserted",
        "trace_id": "..."
    }
    """
    trace_id = get_trace_id(request)
    doc = data.dict()
    doc["_timestamp"] = datetime.now(timezone.utc)
    result = await sensor_collection.insert_one(doc)
    logger.info(f"[trace={trace_id}] Sensor data inserted: session={data.session_id}")
    return {
        "status": "success",
        "session_id": data.session_id,
        "data": {"inserted_id": str(result.inserted_id)},
        "message": "Sensor data inserted",
        "trace_id": trace_id
    }

@router.post(
    "/upload",
    summary="Upload raw sensor data CSV file",
    description="Upload a CSV file containing raw sensor data to be stored in the database."
)
async def upload_raw_csv(file: UploadFile = File(...), request: Request = None, _user=Depends(role_required_dep("editor"))) -> Dict[str, Any]:
    """
    Upload and process a raw sensor data CSV file.
    Expected CSV format: session_id,label,flex1,flex2,flex3,flex4,flex5,accel_x,accel_y,accel_z,gyro_x,gyro_y,gyro_z
    """
    trace_id = get_trace_id(request) if request else "upload"
    
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV file")
    
    try:
        # Read CSV content
        content = await file.read()
        df = pd.read_csv(io.StringIO(content.decode('utf-8')))
        
        # Validate CSV structure
        required_columns = ['session_id', 'label']
        sensor_columns = [f'flex{i}' for i in range(1, 6)] + ['accel_x', 'accel_y', 'accel_z', 'gyro_x', 'gyro_y', 'gyro_z']
        
        # Check if we have either the new format or old format
        if all(col in df.columns for col in required_columns + sensor_columns):
            # New format with separate sensor columns
            pass
        elif 'values' in df.columns and len(required_columns) <= len([col for col in required_columns if col in df.columns]):
            # Old format with values array
            sensor_columns = ['values']
        else:
            raise HTTPException(
                status_code=400, 
                detail=f"CSV must contain columns: {required_columns + sensor_columns} or {required_columns + ['values']}"
            )
        
        # Process and insert data
        documents = []
        for _, row in df.iterrows():
            if 'values' in df.columns:
                # Handle old format
                values = eval(row['values']) if isinstance(row['values'], str) else row['values']
                if not isinstance(values, list) or len(values) != 11:
                    continue  # Skip invalid rows
            else:
                # Handle new format
                values = [row[col] for col in sensor_columns]
                if len(values) != 11:
                    continue  # Skip invalid rows
            
            doc = {
                "session_id": str(row.get('session_id', f"upload_{trace_id}_{len(documents)}")),
                "label": str(row.get('label', 'unknown')),
                "values": values,
                "source": "csv_upload",
                "timestamp": datetime.now(timezone.utc),
                "_timestamp": datetime.now(timezone.utc)
            }
            documents.append(doc)
        
        if not documents:
            raise HTTPException(status_code=400, detail="No valid sensor data found in CSV")
        
        # Insert into database
        result = await sensor_collection.insert_many(documents)
        
        logger.info(f"[trace={trace_id}] Uploaded {len(documents)} sensor data rows from CSV: {file.filename}")
        
        return {
            "status": "success",
            "message": f"Successfully uploaded {len(documents)} sensor data rows",
            "rows_processed": len(documents),
            "inserted_ids": [str(id) for id in result.inserted_ids],
            "trace_id": trace_id
        }
        
    except pd.errors.EmptyDataError:
        raise HTTPException(status_code=400, detail="CSV file is empty")
    except pd.errors.ParserError as e:
        raise HTTPException(status_code=400, detail=f"CSV parsing error: {str(e)}")
    except Exception as e:
        logger.error(f"[trace={trace_id}] CSV upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process CSV file: {str(e)}")

@router.put(
    "/{session_id}",
    summary="Update gesture label for a session",
    description="Update the gesture label for a specific session by session_id."
)
async def update_label(session_id: str, label: str, request: Request, _user=Depends(role_required_dep("editor"))) -> Dict[str, Any]:
    """
    Example response:
    {
        "status": "success",
        "data": {"updated": 1},
        "message": "Gesture label updated",
        "trace_id": "..."
    }
    """
    trace_id = get_trace_id(request)
    result = await sensor_collection.update_one(
        {"session_id": session_id},
        {"$set": {"gesture_label": label}}
    )
    if result.matched_count == 0:
        logger.warning(f"[trace={trace_id}] Session not found for update: {session_id}")
        raise HTTPException(status_code=404, detail="Session not found")
    logger.info(f"[trace={trace_id}] Label updated for session {session_id} to '{label}'")
    return {
        "status": "success",
        "data": {"updated": result.modified_count},
        "message": "Gesture label updated",
        "trace_id": trace_id
    }

@router.delete(
    "/{session_id}",
    summary="Delete sensor data for a session",
    description="Delete all sensor data for a specific session by session_id."
)
async def delete_sensor_data(session_id: str, request: Request, _user=Depends(role_required_dep("editor"))) -> Dict[str, Any]:
    """
    Example response:
    {
        "status": "success",
        "data": {"deleted": 1},
        "message": "Session deleted",
        "trace_id": "..."
    }
    """
    trace_id = get_trace_id(request)
    result = await sensor_collection.delete_one({"session_id": session_id})
    if result.deleted_count == 0:
        logger.warning(f"[trace={trace_id}] Session not found for delete: {session_id}")
        raise HTTPException(status_code=404, detail="Session not found")
    logger.info(f"[trace={trace_id}] Deleted session: {session_id}")
    return {
        "status": "success",
        "data": {"deleted": result.deleted_count},
        "message": "Session deleted",
        "trace_id": trace_id
    }
