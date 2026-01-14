from fastapi import APIRouter
import os
from core.settings import settings

router = APIRouter()

@router.get("/model/status")
async def get_model_status():
    model_exists = os.path.exists(settings.MODEL_PATH)
    metrics_exists = os.path.exists(settings.METRICS_PATH)

    status = {
        "singleHand": model_exists,
        "dualHand": False,  # update if you implement dual-hand models
        "lastUpdated": os.path.getmtime(settings.MODEL_PATH) if model_exists else None,
        "error": None if model_exists else "No trained models available"
    }
    return status
