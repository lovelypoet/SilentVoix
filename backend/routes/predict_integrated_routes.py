import base64
import cv2
import numpy as np
from fastapi import APIRouter, HTTPException, Depends, Body
from services.gesture_service import get_gesture_service
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
    Expects JSON: {"image_data": "data:image/jpeg;base64,..."}
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
            "buffer_status": f"{len(service.frame_buffer)}/{service.sequence_length}"
        }
        
    except Exception as e:
        logger.error(f"Prediction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reset", summary="Reset temporal buffer")
async def reset_integrated(service = Depends(get_gesture_service)) -> Dict[str, Any]:
    service.reset_buffer()
    return {"status": "success", "message": "Buffer cleared"}
