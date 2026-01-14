"""
API routes for managing model training and results in the sign glove system.

Endpoints:
- POST /training/: Save a training result manually.
- GET /training/: List all training results.
- GET /training/{session_id}: Fetch a training result by session ID.
- POST /training/run: Upload CSV, run training, and log result.
- GET /training/metrics: Fetch detailed training metrics and visualizations.
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from models.model_result import ModelResult
from core.database import model_collection, sensor_collection
from fastapi.responses import JSONResponse, FileResponse
from datetime import datetime, timezone
from uuid import uuid4
from core.settings import settings
import logging
import subprocess
import shutil
import os
import json
import sys
from utils.cache import cacheable
from typing import Dict, Any, List
import csv
from routes.auth_routes import role_required_dep, role_or_internal_dep

router = APIRouter(prefix="/training", tags=["Training"])

@router.post("/")
async def save_model_result(result: ModelResult, _user=Depends(role_or_internal_dep("editor"))):
    """
    Save a training result to the database.
    """
    try:
        res = await model_collection.insert_one(result.model_dump())
        logging.info(f"Inserted training result: {res.inserted_id}")
        return JSONResponse(status_code=201, content={
            "status": "success",
            "data": {"inserted_id": str(res.inserted_id)}
        })
    except Exception as e:
        logging.error(f"Error saving model result: {e}")
        raise HTTPException(status_code=500, detail="Failed to save model result")

@router.get(
    "/",
    summary="List all training results",
    description="Returns a list of all training results, sorted by timestamp (most recent first)."
)
@cacheable(ttl=30)
async def list_training_results() -> Dict[str, Any]:
    """
    Example response:
    {
        "status": "success",
        "data": [
            {"session_id": "abc123", "accuracy": 0.98, ...},
            ...
        ]
    }
    """
    try:
        # Check if model_collection is available
        if model_collection is None:
            return {"status": "success", "data": []}
            
        cursor = model_collection.find().sort("timestamp", -1)
        results = []
        async for doc in cursor:
            doc["_id"] = str(doc["_id"])
            results.append(doc)
        logging.info(f"Fetched {len(results)} training results")
        return {"status": "success", "data": results}
    except Exception as e:
        logging.error(f"Error listing training results: {e}")
        return {"status": "success", "data": []}

@router.get("/latest")
async def get_latest_training_result():
    """
    Fetch the most recent training result.
    """
    try:
        # Check if model_collection is available
        if model_collection is None:
            logging.warning("Database connection not available for training results")
            return {"status": "success", "data": None}
            
        result = await model_collection.find_one(sort=[("timestamp", -1)])
        if not result:
            logging.info("No training results found in database")
            return {"status": "success", "data": None}
        result["_id"] = str(result["_id"])
        return {"status": "success", "data": result}
    except Exception as e:
        logging.error(f"Error getting latest training result: {e}")
        return {"status": "success", "data": None}

@router.get(
    "/{session_id}",
    summary="Get a training result by session ID",
    description="Fetch a specific training result by its session_id."
)
@cacheable(ttl=30)
async def get_training_result(session_id: str) -> Dict[str, Any]:
    """
    Example response:
    {
        "status": "success",
        "data": { ... }
    }
    """
    try:
        doc = await model_collection.find_one({"session_id": session_id})
        if not doc:
            raise HTTPException(status_code=404, detail="Training result not found")
        doc["_id"] = str(doc["_id"])
        return {"status": "success", "data": doc}
    except Exception as e:
        logging.error(f"Error fetching training result: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch training result")

@router.get("/metrics/latest")
async def get_latest_training_metrics():
    """
    Fetch the latest training metrics including confusion matrix, ROC curves, and performance data.
    """
    try:
        metrics_path = settings.METRICS_PATH
        
        if not os.path.exists(metrics_path):
            raise HTTPException(status_code=404, detail="No training metrics found. Please run training first.")
        
        with open(metrics_path, 'r') as f:
            content = f.read()
            # Replace NaN and infinity values with null for valid JSON
            content = content.replace('NaN', 'null')
            content = content.replace('Infinity', 'null')
            content = content.replace('-Infinity', 'null')
            
            # Parse and re-serialize to ensure all float values are JSON compliant
            import re
            # Find any remaining problematic float values and replace with null
            content = re.sub(r'\b(?:inf|infinity|-inf|-infinity)\b', 'null', content, flags=re.IGNORECASE)
            
            metrics = json.loads(content)
        
        return {
            "status": "success",
            "data": metrics
        }
    except json.JSONDecodeError as e:
        logging.error(f"Invalid JSON in metrics file: {e}")
        raise HTTPException(status_code=500, detail="Training metrics file is corrupted. Please retrain the model.")
    except Exception as e:
        logging.error(f"Error fetching training metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch training metrics")

@router.get("/visualizations/{plot_type}")
async def get_training_visualization(plot_type: str):
    """
    Fetch training visualization plots.
    plot_type: 'confusion_matrix', 'roc_curves', 'training_history'
    """
    try:
        ai_dir = settings.AI_DIR
        
        plot_files = {
            'confusion_matrix': 'confusion_matrix.png',
            'roc_curves': 'roc_curves.png', 
            'training_history': 'training_history.png'
        }
        
        if plot_type not in plot_files:
            raise HTTPException(status_code=400, detail=f"Invalid plot type. Must be one of: {list(plot_files.keys())}")
        
        plot_path = os.path.join(settings.RESULTS_DIR, plot_files[plot_type])
        
        if not os.path.exists(plot_path):
            raise HTTPException(status_code=404, detail=f"Plot {plot_type} not found. Please run training first.")
        
        return FileResponse(plot_path, media_type="image/png")
    except Exception as e:
        logging.error(f"Error fetching visualization {plot_type}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch {plot_type} visualization")

@router.post("/run")
async def run_training(file: UploadFile = File(...), dual_hand: bool = False, _user=Depends(role_or_internal_dep("editor"))):
    """
    Upload a CSV file, run the training script, and log the result.
    Set dual_hand=True for dual-hand training data.
    """
    try:
        os.makedirs(settings.AI_DIR, exist_ok=True)
        file_path = settings.GESTURE_DUALHAND_DATA_PATH if dual_hand else settings.GESTURE_DATA_PATH
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Run the model.py script with absolute path and stream logs
        script_path = os.path.join(os.path.dirname(__file__), '..', 'AI', 'model.py')
        # Pass the file path as an environment variable so model.py knows which file to use
        env = os.environ.copy()
        env['GESTURE_DATA_FILE'] = file_path
        os.makedirs(os.path.dirname(settings.TRAINING_LOG_PATH), exist_ok=True)
        with open(settings.TRAINING_LOG_PATH, 'w', encoding='utf-8') as logf:
            logf.write("=== Training started ===\n")
        # Start process without waiting to finish; background task tail will parse later
        proc = subprocess.Popen(
            ["python", script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env
        )
        # Stream lines to log in a background thread
        import threading
        def _stream_logs():
            with open(settings.TRAINING_LOG_PATH, 'a', encoding='utf-8') as logf:
                for line in proc.stdout:  # type: ignore[arg-type]
                    logf.write(line)
            proc.wait()
            with open(settings.TRAINING_LOG_PATH, 'a', encoding='utf-8') as logf:
                logf.write(f"\n=== Training finished with code {proc.returncode} ===\n")
        threading.Thread(target=_stream_logs, daemon=True).start()

        return {"status": "started", "message": "Training started. Tail /utils/training/logs to view progress."}

    except Exception as e:
        logging.error(f"Training run failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to run training")

@router.post("/trigger")
async def trigger_training_run(dual_hand: bool = False, _user=Depends(role_or_internal_dep("editor"))):
    """
    Trigger the model training job (same as POST /training/run but without upload).
    Set dual_hand=True to use dual-hand data for training.
    """
    try:
        # Export latest sensor data from MongoDB to CSV so training uses fresh data
        export_path = settings.GESTURE_DUALHAND_DATA_PATH if dual_hand else settings.GESTURE_DATA_PATH
        os.makedirs(os.path.dirname(export_path), exist_ok=True)
        cursor = sensor_collection.find().sort("timestamp", 1)
        rows: List[Dict[str, Any]] = []
        async for doc in cursor:
            values = doc.get("values", [])
            # Support both single-hand (11 values) and dual-hand (22 values)
            if isinstance(values, list) and len(values) in [11, 22]:
                rows.append({
                    "session_id": doc.get("session_id", "auto"),
                    "label": doc.get("label", "unknown"),
                    "values": values
                })
        if not rows:
            logging.warning("No sensor data found to export for training. Using existing CSV if present.")
            # If there are no rows and the CSV does not exist, return 400 instead of failing later
            if not os.path.exists(export_path):
                raise HTTPException(status_code=400, detail="No training data available. Collect data first.")
        else:
            # Determine header based on data dimensions
            sample_values = rows[0]["values"] if rows else []
            if len(sample_values) == 11:
                # Single-hand header
                header = [
                    "session_id", "label",
                    "flex1", "flex2", "flex3", "flex4", "flex5",
                    "accel_x", "accel_y", "accel_z",
                    "gyro_x", "gyro_y", "gyro_z"
                ]
            elif len(sample_values) == 22:
                # Dual-hand header
                header = [
                    "session_id", "label",
                    # Left hand
                    "left_flex1", "left_flex2", "left_flex3", "left_flex4", "left_flex5",
                    "left_accel_x", "left_accel_y", "left_accel_z",
                    "left_gyro_x", "left_gyro_y", "left_gyro_z",
                    # Right hand
                    "right_flex1", "right_flex2", "right_flex3", "right_flex4", "right_flex5",
                    "right_accel_x", "right_accel_y", "right_accel_z",
                    "right_gyro_x", "right_gyro_y", "right_gyro_z"
                ]
            else:
                raise HTTPException(status_code=400, detail=f"Invalid data dimensions: {len(sample_values)}. Expected 11 or 22 values.")
            with open(export_path, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(header)
                for r in rows:
                    writer.writerow([r["session_id"], r["label"], *r["values"]])
            hand_type = "single-hand" if len(sample_values) == 11 else "dual-hand"
            logging.info(f"Exported {len(rows)} {hand_type} sensor rows to {export_path} for training.")

        # Start model.py and stream logs
        script_path = os.path.join(os.path.dirname(__file__), '..', 'AI', 'model.py')
        # Pass the file path as an environment variable so model.py knows which file to use
        env = os.environ.copy()
        env['GESTURE_DATA_FILE'] = export_path
        os.makedirs(os.path.dirname(settings.TRAINING_LOG_PATH), exist_ok=True)
        with open(settings.TRAINING_LOG_PATH, 'w', encoding='utf-8') as logf:
            logf.write("=== Training started ===\n")
        proc = subprocess.Popen(
            ["python", script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env
        )
        import threading
        def _stream_logs():
            with open(settings.TRAINING_LOG_PATH, 'a', encoding='utf-8') as logf:
                for line in proc.stdout:  # type: ignore[arg-type]
                    logf.write(line)
            proc.wait()
            with open(settings.TRAINING_LOG_PATH, 'a', encoding='utf-8') as logf:
                logf.write(f"\n=== Training finished with code {proc.returncode} ===\n")
        threading.Thread(target=_stream_logs, daemon=True).start()

        return {"status": "started", "message": "Training started. Tail /utils/training/logs to view progress."}

    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Triggered training failed: {e}")
        raise HTTPException(status_code=500, detail="Training failed")

@router.post("/dual-hand/run")
async def run_dual_hand_training(file: UploadFile = File(...), _user=Depends(role_or_internal_dep("editor"))):
    """
    Upload a dual-hand CSV file and run training specifically for dual-hand data.
    """
    return await run_training(file, dual_hand=True, _user=_user)

@router.post("/dual-hand/trigger")
async def trigger_dual_hand_training(_user=Depends(role_or_internal_dep("editor"))):
    """
    Trigger dual-hand model training using existing dual-hand data.
    """
    return await trigger_training_run(dual_hand=True, _user=_user)

@router.get("/dual-hand/data")
async def get_dual_hand_data():
    """
    Get dual-hand training data from CSV file.
    """
    try:
        if not os.path.exists(settings.GESTURE_DUALHAND_DATA_PATH):
            raise HTTPException(status_code=404, detail="Dual-hand data file not found")
        
        data = []
        with open(settings.GESTURE_DUALHAND_DATA_PATH, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                data.append(row)
        
        return {
            "status": "success",
            "data": data,
            "count": len(data),
            "type": "dual-hand"
        }
    except Exception as e:
        logging.error(f"Error reading dual-hand data: {e}")
        raise HTTPException(status_code=500, detail="Failed to read dual-hand data")

@router.get("/data/info")
async def get_data_info():
    """
    Get information about available training data files.
    """
    try:
        info = {
            "single_hand": {
                "gesture_data": os.path.exists(settings.GESTURE_DATA_PATH),
                "raw_data": os.path.exists(settings.RAW_DATA_PATH)
            },
            "dual_hand": {
                "gesture_data": os.path.exists(settings.GESTURE_DUALHAND_DATA_PATH),
                "raw_data": os.path.exists(settings.RAW_DUALHAND_DATA_PATH)
            }
        }
        
        # Count rows in each file if it exists
        for hand_type in ["single_hand", "dual_hand"]:
            for data_type in ["gesture_data", "raw_data"]:
                if info[hand_type][data_type]:
                    file_path = getattr(settings, f"{data_type.upper().replace('_DATA', '_DATA_PATH')}" if hand_type == "single_hand" else f"{data_type.upper().replace('_DATA', '_DUALHAND_DATA_PATH')}")
                    try:
                        with open(file_path, 'r') as f:
                            row_count = sum(1 for line in f) - 1  # Subtract header
                        info[hand_type][f"{data_type}_rows"] = row_count
                    except:
                        info[hand_type][f"{data_type}_rows"] = 0
        
        return {
            "status": "success",
            "data": info
        }
    except Exception as e:
        logging.error(f"Error getting data info: {e}")
        raise HTTPException(status_code=500, detail="Failed to get data info")

@router.post("/convert-to-dual-hand/{session_id}")
async def convert_gesture_to_dual_hand(session_id: str, _user=Depends(role_or_internal_dep("editor"))):
    """
    Convert a single-hand gesture (11 values) to dual-hand format (22 values).
    Duplicates the single-hand data for both left and right hands.
    """
    try:
        # Find the gesture in the sensor collection
        gesture = await sensor_collection.find_one({"session_id": session_id})
        if not gesture:
            raise HTTPException(status_code=404, detail="Gesture not found")
        
        values = gesture.get("values", [])
        if len(values) != 11:
            raise HTTPException(status_code=400, detail="Gesture must have exactly 11 values to convert to dual-hand")
        
        # Create dual-hand values by duplicating single-hand data
        # Format: [left_hand_11_values, right_hand_11_values]
        dual_hand_values = values + values  # 22 values total
        
        # Create new session_id for dual-hand version
        new_session_id = f"{session_id}_dual"
        
        # Check if dual-hand version already exists
        existing_dual = await sensor_collection.find_one({"session_id": new_session_id})
        if existing_dual:
            raise HTTPException(status_code=409, detail="Dual-hand version already exists")
        
        # Create new dual-hand gesture document
        dual_hand_gesture = {
            "session_id": new_session_id,
            "label": gesture.get("label", "unknown"),
            "values": dual_hand_values,
            "timestamp": datetime.utcnow(),
            "source": "converted_from_single_hand",
            "original_session_id": session_id
        }
        
        # Insert the new dual-hand gesture
        result = await sensor_collection.insert_one(dual_hand_gesture)
        
        return {
            "status": "success",
            "message": "Gesture converted to dual-hand format",
            "data": {
                "original_session_id": session_id,
                "new_session_id": new_session_id,
                "original_values_count": len(values),
                "new_values_count": len(dual_hand_values),
                "inserted_id": str(result.inserted_id)
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error converting gesture to dual-hand: {e}")
        raise HTTPException(status_code=500, detail="Failed to convert gesture to dual-hand")

@router.get("/conversion-status/{session_id}")
async def check_conversion_status(session_id: str):
    """
    Check if a gesture has been converted to dual-hand format.
    """
    try:
        # Check for dual-hand version
        dual_session_id = f"{session_id}_dual"
        dual_gesture = await sensor_collection.find_one({"session_id": dual_session_id})
        
        return {
            "status": "success",
            "data": {
                "has_dual_hand_version": dual_gesture is not None,
                "dual_hand_session_id": dual_session_id if dual_gesture else None
            }
        }
    except Exception as e:
        logging.error(f"Error checking conversion status: {e}")
        raise HTTPException(status_code=500, detail="Failed to check conversion status")

@router.post("/analyze-confusion-matrix")
async def analyze_confusion_matrix(_user=Depends(role_or_internal_dep("editor"))):
    """
    Run improved confusion matrix analysis on the current gesture data.
    """
    try:
        import subprocess
        import json
        
        # Path to the improved confusion matrix script
        script_path = os.path.join(os.path.dirname(__file__), '..', 'AI', 'improved_confusion_matrix.py')
        
        if not os.path.exists(script_path):
            raise HTTPException(status_code=500, detail="Improved confusion matrix script not found")
        
        # Run the script
        result = subprocess.run([sys.executable, script_path], 
                              capture_output=True, text=True, cwd=os.path.dirname(script_path))
        
        if result.returncode != 0:
            logging.error(f"Script execution failed: {result.stderr}")
            raise HTTPException(status_code=500, detail=f"Analysis failed: {result.stderr}")
        
        # Check if results file was created
        results_path = os.path.join(os.path.dirname(__file__), '..', 'AI', 'results', 'confusion_matrix_results.json')
        
        if not os.path.exists(results_path):
            raise HTTPException(status_code=500, detail="Results file not created")
        
        # Read and return results
        with open(results_path, 'r') as f:
            results = json.load(f)
        
        if results.get('status') == 'success':
            return {
                "status": "success",
                "message": "Confusion matrix analysis completed successfully",
                "data": results
            }
        elif results.get('status') == 'insufficient_data':
            return {
                "status": "error",
                "message": results.get('message', 'Insufficient data for analysis'),
                "data": results
            }
        else:
            return {
                "status": "error", 
                "message": results.get('message', 'Analysis failed'),
                "data": results
            }
            
    except Exception as e:
        logging.error(f"Error running confusion matrix analysis: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to run confusion matrix analysis: {str(e)}")

@router.get("/confusion-matrix/improved")
async def get_improved_confusion_matrix():
    """
    Get the improved confusion matrix visualization.
    """
    try:
        plot_path = os.path.join(os.path.dirname(__file__), '..', 'AI', 'results', 'improved_confusion_matrix.png')
        
        if not os.path.exists(plot_path):
            raise HTTPException(status_code=404, detail="Improved confusion matrix not found. Run analysis first.")
        
        return FileResponse(plot_path, media_type="image/png")
    except Exception as e:
        logging.error(f"Error fetching improved confusion matrix: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch improved confusion matrix")

@router.get("/confusion-matrix/results")
async def get_confusion_matrix_results():
    """
    Get detailed confusion matrix analysis results.
    """
    try:
        results_path = os.path.join(os.path.dirname(__file__), '..', 'AI', 'results', 'confusion_matrix_results.json')
        
        if not os.path.exists(results_path):
            raise HTTPException(status_code=404, detail="Confusion matrix results not found. Run analysis first.")
        
        with open(results_path, 'r') as f:
            results = json.load(f)
        
        return {
            "status": "success",
            "data": results
        }
    except Exception as e:
        logging.error(f"Error fetching confusion matrix results: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch confusion matrix results")