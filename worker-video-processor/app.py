import os
import json
import logging
import uuid
import asyncio
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from concurrent.futures import ProcessPoolExecutor

import cv2
import numpy as np
import torch
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, BackgroundTasks
from pydantic import BaseModel, Field
from ultralytics import YOLO
import mediapipe as mp

# Add current dir to path for imports if needed
import sys
# We'll assume the pipeline logic is copied or shared
# For simplicity in this worker, we'll embed the core pipeline logic or import if mounted

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
logger = logging.getLogger("worker-video-processor")

JOB_DIR = Path(os.getenv("VIDEO_PROCESS_JOB_DIR", "/app/data/video_process_jobs")).resolve()
OUTPUT_DIR = Path(os.getenv("VIDEO_PROCESS_OUTPUT_DIR", "/app/data/video_process_outputs")).resolve()
MODEL_DIR = Path(os.getenv("MODEL_DIR", "/app/AI/models")).resolve()

JOB_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="SilentVoix Video Processor Worker", version="1.0")

# --- MODEL LOADING (Lazy) ---
_models = {}

def get_models():
    if "yolo" not in _models:
        yolo_path = MODEL_DIR / "best.pt"
        if not yolo_path.exists():
            logger.warning(f"YOLO model not found at {yolo_path}, using default")
            _models["yolo"] = YOLO("yolov8n.pt") # Fallback
        else:
            _models["yolo"] = YOLO(str(yolo_path))
            
    if "mp_hands" not in _models:
        _models["mp_hands"] = mp.solutions.hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
    return _models["yolo"], _models["mp_hands"]

# --- SCHEMAS ---
class ProcessOptions(BaseModel):
    generate_overlay: bool = True
    calculate_metrics: bool = True
    compress_video: bool = True
    target_bitrate: str = "1M"

class JobStatus(BaseModel):
    job_id: str
    status: str
    created_at: str
    completed_at: Optional[str] = None
    progress: float = 0.0
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

# --- CORE LOGIC ---
def _clip_box(x1, y1, x2, y2, width, height):
    x1 = max(0, min(int(x1), width - 1))
    y1 = max(0, min(int(y1), height - 1))
    x2 = max(0, min(int(x2), width))
    y2 = max(0, min(int(y2), height))
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2

def _preprocess_landmarks(landmarks):
    kp = np.array([[lm.x, lm.y] for lm in landmarks], dtype=np.float32)
    if kp.shape[0] == 0:
        return np.zeros(63, dtype=np.float32)
    wrist = kp[0]
    kp_centered = kp - wrist
    flat = []
    for p in kp_centered:
        flat.extend([float(p[0]), float(p[1]), 0.0])
    return np.array(flat, dtype=np.float32)

async def run_processing_task(job_id: str, video_path: str, gt_path: Optional[str], options: ProcessOptions):
    job_file = JOB_DIR / f"{job_id}.json"
    status_data = json.loads(job_file.read_text())
    
    try:
        yolo, hands = get_models()
        cap = cv2.VideoCapture(video_path)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        output_video_path = OUTPUT_DIR / f"{job_id}_processed.mp4"
        writer = None
        if options.generate_overlay:
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            writer = cv2.VideoWriter(str(output_video_path), fourcc, fps, (width, height))
            
        status_data["status"] = "processing"
        job_file.write_text(json.dumps(status_data))
        
        predictions = []
        # For simplicity, we'll use a local buffer here
        buffer = []
        sequence_length = 16
        
        for frame_idx in range(total_frames):
            ret, frame = cap.read()
            if not ret: break
            
            # YOLO -> MediaPipe
            found_hand = False
            ui_landmarks = None
            current_bbox = None
            feature = np.zeros(63, dtype=np.float32)
            
            results = yolo(frame, verbose=False, conf=0.5)[0]
            if results.boxes is not None and len(results.boxes) > 0:
                box = results.boxes.xyxy[0].cpu().numpy()
                clipped = _clip_box(*box, width=width, height=height)
                if clipped:
                    x1, y1, x2, y2 = clipped
                    current_bbox = [x1, y1, x2, y2]
                    crop = frame[y1:y2, x1:x2]
                    if crop.size != 0:
                        rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
                        mp_result = hands.process(rgb)
                        if mp_result.multi_hand_landmarks:
                            landmarks = mp_result.multi_hand_landmarks[0].landmark
                            feature = _preprocess_landmarks(landmarks)
                            found_hand = True
                            crop_h, crop_w = crop.shape[:2]
                            ui_landmarks = [[(x1 + lm.x * crop_w)/width, (y1 + lm.y * crop_h)/height] for lm in landmarks]

            buffer.append(feature)
            if len(buffer) > sequence_length: buffer.pop(0)
            
            # Prediction (Dummy for now or load LSTM if available)
            gesture = "Waiting..."
            confidence = 0.0
            
            # Draw overlays
            if writer:
                p_frame = frame.copy()
                if current_bbox:
                    cv2.rectangle(p_frame, (current_bbox[0], current_bbox[1]), (current_bbox[2], current_bbox[3]), (0, 255, 0), 2)
                if ui_landmarks:
                    for pt in ui_landmarks:
                        cv2.circle(p_frame, (int(pt[0]*width), int(pt[1]*height)), 3, (255, 0, 0), -1)
                cv2.putText(p_frame, f"{gesture}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                writer.write(p_frame)
                
            predictions.append({"frame": frame_idx, "gesture": gesture})
            
            if frame_idx % 10 == 0:
                status_data["progress"] = round(frame_idx / total_frames, 2)
                job_file.write_text(json.dumps(status_data))

        cap.release()
        if writer: writer.release()
        
        status_data["status"] = "completed"
        status_data["progress"] = 1.0
        status_data["completed_at"] = datetime.now(timezone.utc).isoformat()
        status_data["result"] = {
            "video_url": f"/outputs/{job_id}_processed.mp4",
            "frame_count": total_frames,
            "predictions": predictions[:100] # Truncated for meta
        }
        job_file.write_text(json.dumps(status_data))
        
    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}")
        status_data["status"] = "failed"
        status_data["error"] = str(e)
        job_file.write_text(json.dumps(status_data))

# --- ROUTES ---
@app.get("/health")
def health():
    return {"status": "ok", "service": "worker-video-processor"}

@app.post("/v1/jobs/process")
async def create_job(
    background_tasks: BackgroundTasks,
    video_file: UploadFile = File(...),
    gt_file: Optional[UploadFile] = File(None),
    options_json: str = Form("{}")
):
    job_id = str(uuid.uuid4())
    options_dict = json.loads(options_json)
    options = ProcessOptions(**options_dict)
    
    # Save uploaded file
    suffix = Path(video_file.filename).suffix or ".mp4"
    video_tmp_path = OUTPUT_DIR / f"{job_id}_input{suffix}"
    with open(video_tmp_path, "wb") as f:
        f.write(await video_file.read())
        
    gt_tmp_path = None
    if gt_file:
        gt_tmp_path = OUTPUT_DIR / f"{job_id}_gt.json"
        with open(gt_tmp_path, "wb") as f:
            f.write(await gt_file.read())
            
    job_status = JobStatus(
        job_id=job_id,
        status="pending",
        created_at=datetime.now(timezone.utc).isoformat()
    )
    
    (JOB_DIR / f"{job_id}.json").write_text(job_status.json())
    
    background_tasks.add_task(run_processing_task, job_id, str(video_tmp_path), str(gt_tmp_path) if gt_tmp_path else None, options)
    
    return job_status

@app.get("/v1/jobs/{job_id}")
async def get_job(job_id: str):
    job_file = JOB_DIR / f"{job_id}.json"
    if not job_file.exists():
        raise HTTPException(status_code=404, detail="Job not found")
    return json.loads(job_file.read_text())
