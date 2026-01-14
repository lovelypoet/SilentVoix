"""
API routes for admin operations in the sign glove system.

Endpoints:
- GET /admin/: Admin API root/status
- DELETE /admin/sensor-data: Delete all sensor data.
- DELETE /admin/training-results: Delete all training results and metrics JSON.
- DELETE /admin/model-files: Delete all model files (.tflite).
- DELETE /admin/training-visualizations: Delete training plots and results directory.
- DELETE /admin/csv-data: Delete all CSV data files.
- DELETE /admin/all-training-data: Comprehensive cleanup of all training artifacts.
"""
from fastapi import APIRouter, HTTPException, Depends
from core.database import sensor_collection, model_collection
import logging
import os
import shutil
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

@router.delete("/training-results")
async def clear_training_results(_user=Depends(role_or_internal_dep("editor"))):
    """
    Delete all training results from the database and training metrics JSON file.
    """
    try:
        # Clear database records
        result = await model_collection.delete_many({})
        logging.info(f"Deleted {result.deleted_count} training results")
        
        # Clear training metrics JSON file
        metrics_file = Path("AI/training_metrics.json")
        if metrics_file.exists():
            metrics_file.unlink()
            logging.info("Deleted training_metrics.json")
        
        return {"status": "success", "deleted": result.deleted_count, "files_cleared": ["training_metrics.json"]}
    except Exception as e:
        logging.error(f"Failed to clear training results: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear training results")

@router.delete("/model-files")
async def clear_model_files(_user=Depends(role_or_internal_dep("editor"))):
    """
    Delete all model files (.tflite files).
    """
    try:
        deleted_files = []
        ai_dir = Path("AI")
        
        if ai_dir.exists():
            # Find and delete all .tflite files
            for model_file in ai_dir.glob("*.tflite"):
                model_file.unlink()
                deleted_files.append(model_file.name)
                logging.info(f"Deleted model file: {model_file.name}")
        
        return {"status": "success", "deleted_files": deleted_files}
    except Exception as e:
        logging.error(f"Failed to clear model files: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear model files")

@router.delete("/training-visualizations")
async def clear_training_visualizations(_user=Depends(role_or_internal_dep("editor"))):
    """
    Delete training visualization plots and clear results directory.
    """
    try:
        deleted_items = []
        
        # Clear AI/results directory
        results_dir = Path("AI/results")
        if results_dir.exists():
            for item in results_dir.iterdir():
                if item.is_file():
                    item.unlink()
                    deleted_items.append(f"results/{item.name}")
                elif item.is_dir():
                    shutil.rmtree(item)
                    deleted_items.append(f"results/{item.name}/")
            logging.info(f"Cleared results directory: {len(deleted_items)} items")
        
        return {"status": "success", "deleted_items": deleted_items}
    except Exception as e:
        logging.error(f"Failed to clear training visualizations: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear training visualizations")

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

@router.delete("/all-training-data")
async def clear_all_training_data(_user=Depends(role_or_internal_dep("editor"))):
    """
    Comprehensive cleanup: Delete all training-related data including database records,
    CSV files, model files, training metrics, and visualization plots.
    """
    try:
        summary = {
            "database_records": 0,
            "deleted_files": [],
            "deleted_items": [],
            "errors": []
        }
        
        # Clear database records
        try:
            sensor_result = await sensor_collection.delete_many({})
            model_result = await model_collection.delete_many({})
            summary["database_records"] = sensor_result.deleted_count + model_result.deleted_count
            logging.info(f"Deleted {summary['database_records']} total database records")
        except Exception as e:
            summary["errors"].append(f"Database cleanup failed: {str(e)}")
        
        # Clear training metrics JSON
        try:
            metrics_file = Path("AI/training_metrics.json")
            if metrics_file.exists():
                metrics_file.unlink()
                summary["deleted_files"].append("training_metrics.json")
        except Exception as e:
            summary["errors"].append(f"Metrics file cleanup failed: {str(e)}")
        
        # Clear model files
        try:
            ai_dir = Path("AI")
            if ai_dir.exists():
                for model_file in ai_dir.glob("*.tflite"):
                    model_file.unlink()
                    summary["deleted_files"].append(model_file.name)
        except Exception as e:
            summary["errors"].append(f"Model files cleanup failed: {str(e)}")
        
        # Clear results directory
        try:
            results_dir = Path("AI/results")
            if results_dir.exists():
                for item in results_dir.iterdir():
                    if item.is_file():
                        item.unlink()
                        summary["deleted_items"].append(f"results/{item.name}")
                    elif item.is_dir():
                        shutil.rmtree(item)
                        summary["deleted_items"].append(f"results/{item.name}/")
        except Exception as e:
            summary["errors"].append(f"Results directory cleanup failed: {str(e)}")
        
        # Clear CSV files
        try:
            data_dir = Path("data")
            if data_dir.exists():
                csv_files = ["raw_data.csv", "gesture_data.csv"]
                for csv_file in csv_files:
                    file_path = data_dir / csv_file
                    if file_path.exists():
                        file_path.unlink()
                        summary["deleted_files"].append(csv_file)
        except Exception as e:
            summary["errors"].append(f"CSV files cleanup failed: {str(e)}")
        
        logging.info(f"Comprehensive cleanup completed: {summary}")
        return {"status": "success", "summary": summary}
        
    except Exception as e:
        logging.error(f"Failed comprehensive cleanup: {e}")
        raise HTTPException(status_code=500, detail="Failed to perform comprehensive cleanup")
