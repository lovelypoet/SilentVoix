"""
API routes for managing model training and results in the sign glove system.

Endpoints:
- POST /training/: Save a training result manually.
- GET /training/: List all training results.
- GET /training/{session_id}: Fetch a training result by session ID.
- POST /training/run: Upload CSV, run training, and log result.
- GET /training/metrics: Fetch detailed training metrics and visualizations.
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, Query
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
import threading
from pathlib import Path
from utils.cache import cacheable
from typing import Dict, Any, List
import csv
import numpy as np
import pandas as pd
from joblib import dump as joblib_dump
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split
from routes.auth_routes import role_required_dep, role_or_internal_dep

router = APIRouter(prefix="/training", tags=["Training"])

LATE_FUSION_SELECTION_FILE = "selected_datasets.json"
LATE_FUSION_JOB_LOCK = threading.Lock()
LATE_FUSION_JOBS: Dict[str, Dict[str, Any]] = {}
LATE_FUSION_LAST_BY_MODE: Dict[str, Dict[str, Any]] = {}
LATE_FUSION_DEFAULT_GLOVE_WEIGHT = 0.8


def _late_fusion_results_dir() -> Path:
    root = Path(settings.RESULTS_DIR) / "late_fusion"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _late_fusion_selection_store_path() -> Path:
    return Path(settings.DATA_DIR) / "csv_library" / LATE_FUSION_SELECTION_FILE


def _late_fusion_list_roots(include_archived: bool = True) -> List[tuple[str, Path]]:
    roots: List[tuple[str, Path]] = []
    active = Path(settings.DATA_DIR) / "csv_library" / "active"
    if active.exists():
        roots.append(("active", active))
    if include_archived:
        archive = Path(settings.DATA_DIR) / "csv_library" / "archive"
        if archive.exists():
            roots.append(("archive", archive))
    legacy = Path(settings.DATA_DIR)
    if legacy.exists():
        roots.append(("legacy", legacy))
    return roots


def _late_fusion_resolve_csv_path(name: str) -> tuple[str, Path]:
    safe_name = str((name or "").strip().replace("\\", "/"))
    if not safe_name:
        raise HTTPException(status_code=400, detail="CSV selection name is missing")
    rel = Path(safe_name)
    if rel.is_absolute() or ".." in rel.parts or rel.suffix.lower() != ".csv":
        raise HTTPException(status_code=400, detail=f"Invalid selected CSV path: {safe_name}")

    for scope, root in _late_fusion_list_roots(include_archived=True):
        candidate = (root / rel).resolve()
        try:
            candidate.relative_to(root.resolve())
        except ValueError:
            continue
        if candidate.exists() and candidate.is_file():
            return scope, candidate
    raise HTTPException(status_code=404, detail=f"Selected CSV file not found: {safe_name}")


def _late_fusion_load_selection(mode: str) -> Dict[str, Any]:
    selection_path = _late_fusion_selection_store_path()
    if not selection_path.exists():
        raise HTTPException(status_code=400, detail="No selected datasets found. Choose datasets in CSV Library first.")
    try:
        with selection_path.open("r", encoding="utf-8") as f:
            store = json.load(f)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read selected datasets store: {exc}")
    if not isinstance(store, dict):
        raise HTTPException(status_code=500, detail="Invalid selected datasets store format")

    cv_key = f"late:{mode}:cv"
    sensor_key = f"late:{mode}:sensor"
    cv_sel = store.get(cv_key)
    sensor_sel = store.get(sensor_key)
    if not cv_sel or not sensor_sel:
        raise HTTPException(
            status_code=400,
            detail=f"Late fusion requires both slots selected for mode={mode} ({cv_key} and {sensor_key})",
        )
    if cv_sel.get("schema_id") != f"cv_{mode}":
        raise HTTPException(status_code=400, detail=f"Selected CV schema must be cv_{mode}")
    if sensor_sel.get("schema_id") != f"sensor_{mode}":
        raise HTTPException(status_code=400, detail=f"Selected Sensor schema must be sensor_{mode}")

    _cv_scope, cv_path = _late_fusion_resolve_csv_path(cv_sel.get("name", ""))
    _sensor_scope, sensor_path = _late_fusion_resolve_csv_path(sensor_sel.get("name", ""))
    return {
        "cv_selection": cv_sel,
        "sensor_selection": sensor_sel,
        "cv_path": cv_path,
        "sensor_path": sensor_path,
    }


def _normalize_sensor_frame(df: pd.DataFrame, mode: str) -> pd.DataFrame:
    work = df.copy()
    if "timestamp_ms" not in work.columns:
        raise HTTPException(status_code=400, detail="Sensor CSV must contain timestamp_ms")
    if "label" not in work.columns:
        if "recording_label" in work.columns:
            work["label"] = work["recording_label"]
        else:
            work["label"] = ""

    if mode == "single":
        mapping = {
            "f1": ("f1", "flex1"),
            "f2": ("f2", "flex2"),
            "f3": ("f3", "flex3"),
            "f4": ("f4", "flex4"),
            "f5": ("f5", "flex5"),
            "ax": ("ax", "accel_x"),
            "ay": ("ay", "accel_y"),
            "az": ("az", "accel_z"),
            "gx": ("gx", "gyro_x"),
            "gy": ("gy", "gyro_y"),
            "gz": ("gz", "gyro_z"),
        }
        for canonical, aliases in mapping.items():
            for alias in aliases:
                if alias in work.columns:
                    work[canonical] = pd.to_numeric(work[alias], errors="coerce")
                    break
            if canonical not in work.columns:
                raise HTTPException(status_code=400, detail=f"Sensor CSV missing required column: {canonical}")
        feature_cols = ["f1", "f2", "f3", "f4", "f5", "ax", "ay", "az", "gx", "gy", "gz"]
    else:
        feature_cols = [
            "left_flex_1", "left_flex_2", "left_flex_3", "left_flex_4", "left_flex_5",
            "left_acc_1", "left_acc_2", "left_acc_3", "left_gyro_1", "left_gyro_2", "left_gyro_3",
            "right_flex_1", "right_flex_2", "right_flex_3", "right_flex_4", "right_flex_5",
            "right_acc_1", "right_acc_2", "right_acc_3", "right_gyro_1", "right_gyro_2", "right_gyro_3",
        ]
        missing = [col for col in feature_cols if col not in work.columns]
        if missing:
            raise HTTPException(status_code=400, detail=f"Sensor CSV missing required columns: {', '.join(missing[:8])}")
        for col in feature_cols:
            work[col] = pd.to_numeric(work[col], errors="coerce")

    work["timestamp_ms"] = pd.to_numeric(work["timestamp_ms"], errors="coerce")
    work["label"] = work["label"].astype(str)
    work = work.dropna(subset=["timestamp_ms"])
    return work[["timestamp_ms", "label", *feature_cols]].sort_values("timestamp_ms")


def _cv_ordered_feature_cols(columns: List[str], mode: str) -> List[str]:
    left = [f"L_{axis}{idx}" for idx in range(21) for axis in ("x", "y", "z")]
    right = [f"R_{axis}{idx}" for idx in range(21) for axis in ("x", "y", "z")]
    cols = set(columns)
    if mode == "single":
        if all(c in cols for c in left):
            return left
        if all(c in cols for c in right):
            return right
        raise HTTPException(status_code=400, detail="CV single CSV must contain a full 63-dim hand landmark set")
    missing_left = [c for c in left if c not in cols]
    missing_right = [c for c in right if c not in cols]
    if missing_left or missing_right:
        raise HTTPException(status_code=400, detail="CV dual CSV must contain full left and right 63-dim landmarks")
    return [*left, *right]


def _normalize_cv_frame(df: pd.DataFrame, mode: str) -> pd.DataFrame:
    work = df.copy()
    if "timestamp_ms" not in work.columns:
        raise HTTPException(status_code=400, detail="CV CSV must contain timestamp_ms")
    if "label" not in work.columns:
        if "gesture" in work.columns:
            work["label"] = work["gesture"]
        else:
            work["label"] = ""
    feature_cols = _cv_ordered_feature_cols(list(work.columns), mode)
    work["timestamp_ms"] = pd.to_numeric(work["timestamp_ms"], errors="coerce")
    for col in feature_cols:
        work[col] = pd.to_numeric(work[col], errors="coerce")
    work["label"] = work["label"].astype(str)
    work = work.dropna(subset=["timestamp_ms"])
    return work[["timestamp_ms", "label", *feature_cols]].sort_values("timestamp_ms")


def _fit_rf_model(X_train: np.ndarray, y_train: np.ndarray, random_state: int = 42) -> RandomForestClassifier:
    model = RandomForestClassifier(
        n_estimators=200,
        random_state=random_state,
        class_weight="balanced",
        n_jobs=-1,
    )
    model.fit(X_train, y_train)
    return model


def _run_late_fusion_training_job(job_id: str, mode: str, glove_weight: float) -> None:
    with LATE_FUSION_JOB_LOCK:
        job = LATE_FUSION_JOBS[job_id]
        job["status"] = "running"
        job["started_at"] = datetime.now(timezone.utc).isoformat()
        job["progress"] = "Loading selected datasets"

    try:
        selection = _late_fusion_load_selection(mode)
        cv_path = selection["cv_path"]
        sensor_path = selection["sensor_path"]
        cv_df = _normalize_cv_frame(pd.read_csv(cv_path), mode)
        sensor_df = _normalize_sensor_frame(pd.read_csv(sensor_path), mode)

        with LATE_FUSION_JOB_LOCK:
            LATE_FUSION_JOBS[job_id]["progress"] = "Aligning CV and sensor rows by timestamp"

        aligned = pd.merge_asof(
            cv_df.sort_values("timestamp_ms"),
            sensor_df.sort_values("timestamp_ms"),
            on="timestamp_ms",
            direction="nearest",
            tolerance=120,
            suffixes=("_cv", "_sensor"),
        )
        aligned = aligned.dropna(subset=["label_cv", "label_sensor"])
        aligned = aligned[aligned["label_cv"] == aligned["label_sensor"]]
        aligned = aligned.dropna(axis=0)
        if aligned.empty or len(aligned) < 20:
            raise HTTPException(status_code=400, detail="Not enough aligned rows for late fusion training")

        cv_features = [c for c in aligned.columns if c.startswith(("L_", "R_"))]
        sensor_features = [c for c in aligned.columns if c in {
            "f1", "f2", "f3", "f4", "f5", "ax", "ay", "az", "gx", "gy", "gz",
            "left_flex_1", "left_flex_2", "left_flex_3", "left_flex_4", "left_flex_5",
            "left_acc_1", "left_acc_2", "left_acc_3", "left_gyro_1", "left_gyro_2", "left_gyro_3",
            "right_flex_1", "right_flex_2", "right_flex_3", "right_flex_4", "right_flex_5",
            "right_acc_1", "right_acc_2", "right_acc_3", "right_gyro_1", "right_gyro_2", "right_gyro_3",
        }]
        if not cv_features or not sensor_features:
            raise HTTPException(status_code=400, detail="Could not determine CV/Sensor feature columns after alignment")

        y = aligned["label_cv"].astype(str).to_numpy()
        X_cv = aligned[cv_features].to_numpy(dtype=np.float32)
        X_sensor = aligned[sensor_features].to_numpy(dtype=np.float32)
        if len(np.unique(y)) < 2:
            raise HTTPException(status_code=400, detail="Late fusion requires at least 2 classes")

        with LATE_FUSION_JOB_LOCK:
            LATE_FUSION_JOBS[job_id]["progress"] = "Splitting train/test and training expert models"

        idx = np.arange(len(y))
        train_idx, test_idx = train_test_split(idx, test_size=0.2, random_state=42, stratify=y)
        cv_model = _fit_rf_model(X_cv[train_idx], y[train_idx], random_state=42)
        sensor_model = _fit_rf_model(X_sensor[train_idx], y[train_idx], random_state=43)

        cv_proba = cv_model.predict_proba(X_cv[test_idx])
        sensor_proba = sensor_model.predict_proba(X_sensor[test_idx])
        classes_cv = list(cv_model.classes_)
        classes_sensor = list(sensor_model.classes_)
        if classes_cv != classes_sensor:
            raise HTTPException(status_code=500, detail="Model class mismatch between CV and Sensor experts")

        vision_weight = 1.0 - glove_weight
        late_proba = (glove_weight * sensor_proba) + (vision_weight * cv_proba)
        pred_idx = np.argmax(late_proba, axis=1)
        y_pred = np.array(classes_cv, dtype=object)[pred_idx]
        y_true = y[test_idx]

        metrics = {
            "accuracy": float(accuracy_score(y_true, y_pred)),
            "macro_f1": float(f1_score(y_true, y_pred, average="macro")),
            "classes": [str(c) for c in classes_cv],
            "train_rows": int(len(train_idx)),
            "test_rows": int(len(test_idx)),
            "aligned_rows": int(len(aligned)),
        }

        with LATE_FUSION_JOB_LOCK:
            LATE_FUSION_JOBS[job_id]["progress"] = "Saving artifacts"

        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        out_dir = _late_fusion_results_dir() / mode / f"{stamp}_{job_id}"
        out_dir.mkdir(parents=True, exist_ok=True)
        cv_model_path = out_dir / "cv_model.joblib"
        sensor_model_path = out_dir / "sensor_model.joblib"
        aligned_preview_path = out_dir / "aligned_preview.csv"
        report_path = out_dir / "report.json"
        joblib_dump(cv_model, cv_model_path)
        joblib_dump(sensor_model, sensor_model_path)
        aligned.head(5000).to_csv(aligned_preview_path, index=False)

        report = {
            "job_id": job_id,
            "mode": mode,
            "status": "succeeded",
            "weights": {"glove": glove_weight, "vision": vision_weight},
            "selected": {
                "cv": selection["cv_selection"],
                "sensor": selection["sensor_selection"],
            },
            "artifacts": {
                "cv_model_path": str(cv_model_path),
                "sensor_model_path": str(sensor_model_path),
                "aligned_preview_path": str(aligned_preview_path),
                "report_path": str(report_path),
            },
            "metrics": metrics,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }
        with report_path.open("w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=True, indent=2)

        latest_path = _late_fusion_results_dir() / mode / "latest.json"
        with latest_path.open("w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=True, indent=2)

        with LATE_FUSION_JOB_LOCK:
            LATE_FUSION_JOBS[job_id]["status"] = "succeeded"
            LATE_FUSION_JOBS[job_id]["finished_at"] = datetime.now(timezone.utc).isoformat()
            LATE_FUSION_JOBS[job_id]["progress"] = "Completed"
            LATE_FUSION_JOBS[job_id]["result"] = report
            LATE_FUSION_LAST_BY_MODE[mode] = report
    except HTTPException as exc:
        with LATE_FUSION_JOB_LOCK:
            LATE_FUSION_JOBS[job_id]["status"] = "failed"
            LATE_FUSION_JOBS[job_id]["finished_at"] = datetime.now(timezone.utc).isoformat()
            LATE_FUSION_JOBS[job_id]["error"] = exc.detail
    except Exception as exc:
        logging.exception("Late fusion training job failed")
        with LATE_FUSION_JOB_LOCK:
            LATE_FUSION_JOBS[job_id]["status"] = "failed"
            LATE_FUSION_JOBS[job_id]["finished_at"] = datetime.now(timezone.utc).isoformat()
            LATE_FUSION_JOBS[job_id]["error"] = str(exc)

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


@router.post("/late-fusion/run")
async def run_late_fusion_training(
    mode: str = Query("single", pattern="^(single|dual)$"),
    glove_weight: float = Query(LATE_FUSION_DEFAULT_GLOVE_WEIGHT, ge=0.0, le=1.0),
    _user=Depends(role_or_internal_dep("editor")),
):
    with LATE_FUSION_JOB_LOCK:
        running_job = next(
            (
                j for j in LATE_FUSION_JOBS.values()
                if j.get("mode") == mode and j.get("status") in {"queued", "running"}
            ),
            None,
        )
        if running_job:
            raise HTTPException(
                status_code=409,
                detail=f"A late fusion training job is already running for mode={mode} ({running_job.get('job_id')})",
            )

        job_id = str(uuid4())
        LATE_FUSION_JOBS[job_id] = {
            "job_id": job_id,
            "type": "late_fusion_training",
            "mode": mode,
            "status": "queued",
            "glove_weight": float(glove_weight),
            "vision_weight": float(1.0 - glove_weight),
            "queued_at": datetime.now(timezone.utc).isoformat(),
            "started_at": None,
            "finished_at": None,
            "progress": "Queued",
            "result": None,
            "error": None,
        }

    worker = threading.Thread(
        target=_run_late_fusion_training_job,
        args=(job_id, mode, float(glove_weight)),
        daemon=True,
    )
    worker.start()
    return {
        "status": "started",
        "job_id": job_id,
        "mode": mode,
        "glove_weight": float(glove_weight),
        "vision_weight": float(1.0 - glove_weight),
    }


@router.get("/late-fusion/jobs/{job_id}")
async def get_late_fusion_job(job_id: str, _user=Depends(role_or_internal_dep("editor"))):
    with LATE_FUSION_JOB_LOCK:
        job = LATE_FUSION_JOBS.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Late fusion job not found: {job_id}")
        return {"status": "success", "job": job}


@router.get("/late-fusion/latest")
async def get_latest_late_fusion_result(
    mode: str = Query("single", pattern="^(single|dual)$"),
    _user=Depends(role_or_internal_dep("editor")),
):
    with LATE_FUSION_JOB_LOCK:
        in_memory = LATE_FUSION_LAST_BY_MODE.get(mode)
    if in_memory:
        return {"status": "success", "mode": mode, "data": in_memory}

    latest_path = _late_fusion_results_dir() / mode / "latest.json"
    if latest_path.exists():
        try:
            with latest_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return {"status": "success", "mode": mode, "data": data}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Failed to read latest late fusion result: {exc}")

    return {"status": "success", "mode": mode, "data": None}

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
