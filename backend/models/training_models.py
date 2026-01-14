"""
Models for training requests, responses, and session tracking in the sign glove system.

- TrainingRequest: Input schema for starting a training job.
- TrainingResponse: Status and timestamp for training initiation.
- TrainingSession: Metadata and results for a completed or ongoing training session.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime

class TrainingRequest(BaseModel):
    """
    Input schema for starting a model training job.
    Attributes:
        model_name (str): Name of the model architecture.
        gestures (Optional[List[str]]): List of gesture labels to train on.
        epochs (Optional[int]): Number of training epochs.
    """
    model_name: str = Field(..., example="LSTM_v1")
    gestures: Optional[List[str]] = Field(default=None, example=["hello", "yes", "no"])
    epochs: Optional[int] = Field(default=20, example=20)

class TrainingResponse(BaseModel):
    """
    Status and timestamp for training initiation.
    Attributes:
        status (str): Status message (e.g., 'training_started').
        started_at (datetime): When training started.
    """
    status: str = Field(..., example="training_started")
    started_at: datetime = Field(..., example="2025-06-27T12:00:00Z")

class TrainingSession(BaseModel):
    """
    Metadata and results for a completed or ongoing training session.
    Attributes:
        model_name (str): Name of the model.
        gestures_used (List[str]): Gestures used in training.
        params (Dict[str, int]): Training parameters (e.g., epochs).
        accuracy (Optional[float]): Final accuracy.
        loss (Optional[float]): Final loss.
        started_at (datetime): Start time.
        completed_at (Optional[datetime]): End time.
        duration_sec (Optional[int]): Duration in seconds.
        notes (Optional[str]): Additional notes.
    """
    model_name: str
    gestures_used: List[str]
    params: Dict[str, int]  # like {"epochs": 20}
    accuracy: Optional[float] = None
    loss: Optional[float] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_sec: Optional[int] = None
    notes: Optional[str] = None
