"""
Model result schema for storing and returning training results in the sign glove system.

- ModelResult: Stores accuracy, model name, timestamp, and optional notes for a training session.
"""
# Pydantic schema for model results

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class ModelResult(BaseModel):
    """
    Stores results of a model training session.
    Attributes:
        session_id (str): Training session ID.
        timestamp (datetime): When training occurred.
        accuracy (float): Model accuracy (0.0 to 1.0).
        model_name (Optional[str]): Name of the model used.
        notes (Optional[str]): Optional training notes.
    """
    session_id: str = Field(..., description="Training session ID")
    timestamp: datetime = Field(..., description="When training occurred")
    accuracy: float = Field(..., ge=0.0, le=1.0, description="Model accuracy (0.0 to 1.0)")
    model_name: Optional[str] = Field(None, description="Name of the model used")
    notes: Optional[str] = Field(None, description="Optional training notes")
