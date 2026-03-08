import base64
import cv2
import numpy as np
import os
from fastapi import APIRouter, HTTPException, Depends, Body
from services.gesture_service import get_gesture_service
from services.playground_service import playground_service
from typing import Dict, Any
import logging

logger = logging.getLogger("signglove.predict")

router = APIRouter(prefix="/predict/integrated", tags=["Prediction"])

@router.post("", summary="Predict gesture using YOLOv8-Pose + LSTM")
async def predict_integrated(
    payload: Dict[str, Any] = Body(...),
    service = Depends(get_gesture_service)
) -> Dict[str, Any]:
    """
    Expects JSON: {"image_data": "data:image/jpeg;base64,...", "model_id": "optional-classifier-id"}
    """
    try:
        image_data = payload.get("image_data")
        if not image_data:
            raise HTTPException(status_code=400, detail="Missing image_data")

        # 1. Decode base64 image
        if "," in image_data:
            header, encoded = image_data.split(",", 1)
        else:
            encoded = image_data
            
        nparr = np.frombuffer(base64.b64decode(encoded), np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if frame is None:
            raise ValueError("Invalid image data")

        # 2. Process frame
        result = service.predict_frame(frame)
        
        return {
            "status": "success",
            "gesture": result["gesture"],
            "confidence": result["confidence"],
            "hand_detected": result["hand_detected"],
            "landmarks": result["landmarks"],
            "buffer_status": f"{len(service.frame_buffer)}/{service.sequence_length}",
            "detector": os.path.basename(service.yolo_path)
        }
        
    except Exception as e:
        logger.error(f"Prediction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/detector", summary="Get active YOLO detector info")
async def get_active_detector(service = Depends(get_gesture_service)):
    registry = playground_service.load_registry()
    current_path = service.yolo_path
    
    # Try to find which entry matches this path
    match = next((m for m in registry.get("models", []) if m.get("model_path") == current_path), None)
    
    return {
        "status": "success",
        "current_path": current_path,
        "model_id": match["id"] if match else None,
        "display_name": match["display_name"] if match else os.path.basename(current_path)
    }

@router.post("/detector/{model_id}", summary="Set active YOLO detector by ID")
async def set_active_detector(model_id: str, service = Depends(get_gesture_service)):
    try:
        service.reload_detector_by_id(model_id)
        return {"status": "success", "message": f"Detector switched to model {model_id}"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/reset", summary="Reset temporal buffer")
async def reset_integrated(service = Depends(get_gesture_service)) -> Dict[str, Any]:
    service.reset_buffer()
    return {"status": "success", "message": "Buffer cleared"}
