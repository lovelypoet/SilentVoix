from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from core.database import feedback_collection
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/model-library/feedback", tags=["Model Feedback"])

class FeedbackCreate(BaseModel):
    model_id: str
    predicted_label: str
    true_label: str
    confidence: float
    session_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

@router.post("")
async def submit_feedback(feedback: FeedbackCreate):
    """
    Submits user feedback for a specific model prediction.
    """
    try:
        feedback_doc = feedback.model_dump()
        feedback_doc["timestamp"] = datetime.now(timezone.utc)
        feedback_doc["is_correct"] = feedback.predicted_label == feedback.true_label
        
        result = await feedback_collection.insert_one(feedback_doc)
        
        logger.info(f"Feedback recorded for model {feedback.model_id}: {'Correct' if feedback_doc['is_correct'] else 'Incorrect'}")
        
        return {
            "status": "success",
            "message": "Feedback recorded",
            "feedback_id": str(result.inserted_id)
        }
    except Exception as e:
        logger.error(f"Failed to record feedback: {e}")
        raise HTTPException(status_code=500, detail="Internal server error recording feedback")

@router.get("/stats/{model_id}")
async def get_model_feedback_stats(model_id: str):
    """
    Returns aggregate feedback stats for a specific model.
    """
    pipeline = [
        {"$match": {"model_id": model_id}},
        {
            "$group": {
                "_id": "$true_label",
                "total": {"$sum": 1},
                "correct": {"$sum": {"$cond": ["$is_correct", 1, 0]}}
            }
        },
        {
            "$project": {
                "label": "$_id",
                "accuracy": {"$divide": ["$correct", "$total"]},
                "total_feedback": "$total",
                "_id": 0
            }
        }
    ]
    
    cursor = feedback_collection.aggregate(pipeline)
    stats = await cursor.to_list(length=1000)
    
    return {
        "status": "success",
        "model_id": model_id,
        "stats": stats
    }
