"""
Response models for API endpoints in the sign glove system.

- UploadResponse: Response after uploading sensor or gesture data.
"""
from pydantic import BaseModel

class UploadResponse(BaseModel):
    """
    Response after uploading sensor or gesture data.
    Attributes:
        message (str): Status or result message.
        session_id (str): Session identifier for the upload.
        samples (int): Number of samples uploaded.
    """
    message: str
    session_id: str
    samples: int

