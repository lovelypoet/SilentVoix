"""
API routes for admin operations in the sign glove system.

Endpoints:
- GET /admin/: Admin API root/status
- DELETE /admin/sensor-data: Delete all sensor data.
- DELETE /admin/csv-data: Delete all CSV data files.
"""
from fastapi import APIRouter, HTTPException, Depends
from core.database import sensor_collection
import logging
from pathlib import Path
from routes.auth_routes import role_or_internal_dep

router = APIRouter(prefix="/admin", tags=["Admin"])

@router.get("/")
async def admin_root():
    """Admin API root endpoint for quick status checks."""
    return {"status": "ok", "service": "admin"}

@router.delete("/sensor-data")
async def clear_sensor_data(_user=Depends(role_or_internal_dep("editor"))):
    """
    Delete all sensor data from the database.
    """
    try:
        result = await sensor_collection.delete_many({})
        logging.info(f"Deleted {result.deleted_count} sensor documents")
        return {"status": "success", "deleted": result.deleted_count}
    except Exception as e:
        logging.error(f"Failed to clear sensor data: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear sensor data")

@router.delete("/csv-data")
async def clear_csv_data(_user=Depends(role_or_internal_dep("editor"))):
    """
    Delete all CSV data files.
    """
    try:
        deleted_files = []
        data_dir = Path("data")
        
        if data_dir.exists():
            # Delete specific CSV files
            csv_files = ["raw_data.csv", "gesture_data.csv"]
            for csv_file in csv_files:
                file_path = data_dir / csv_file
                if file_path.exists():
                    file_path.unlink()
                    deleted_files.append(csv_file)
                    logging.info(f"Deleted CSV file: {csv_file}")
        
        return {"status": "success", "deleted_files": deleted_files}
    except Exception as e:
        logging.error(f"Failed to clear CSV data: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear CSV data")
