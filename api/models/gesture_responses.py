"""
Models for gesture sample data and upload requests in the sign glove system.

- GestureSample: Represents a single gesture sample with flex and IMU values.
- GestureUpload: Structure for uploading a batch of gesture samples with session and label info.
"""
from pydantic import BaseModel, Field
from typing import List
from datetime import datetime

class GestureSample(BaseModel):
    """
    Represents a single gesture sample.
    Attributes:
        flex_values (List[int]): Flex sensor readings.
        imu_values (List[float]): IMU sensor readings.
    """
    flex_values: List[int]
    imu_values: List[float]

class GestureUpload(BaseModel):
    """
    Structure for uploading a batch of gesture samples.
    Attributes:
        session_id (str): Session identifier.
        label (str): Gesture label.
        samples (List[GestureSample]): List of gesture samples.
        timestamp (datetime): Upload timestamp.
    """
    session_id: str
    label: str
    samples: List[GestureSample]
    timestamp: datetime
