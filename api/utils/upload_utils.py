import os
import shutil
from pathlib import Path
from fastapi import UploadFile, HTTPException
from api.core.settings import settings
import logging

logger = logging.getLogger("signglove.upload_utils")

async def handle_streaming_upload(
    file: UploadFile, 
    max_size: int, 
    allowed_extensions: list = None
) -> Path:
    """
    Saves an UploadFile in chunks to a temporary directory, enforcing size limits.
    """
    if allowed_extensions:
        ext = Path(file.filename or "").suffix.lower()
        if ext not in allowed_extensions:
            raise HTTPException(
                status_code=400, 
                detail=f"File extension {ext} not allowed. Supported: {allowed_extensions}"
            )

    # Ensure tmp directory exists
    os.makedirs(settings.UPLOAD_TMP_DIR, exist_ok=True)
    
    tmp_path = Path(settings.UPLOAD_TMP_DIR) / f"{os.urandom(8).hex()}_{file.filename}"
    
    size = 0
    try:
        with open(tmp_path, "wb") as buffer:
            while True:
                chunk = await file.read(1024 * 1024) # 1MB chunks
                if not chunk:
                    break
                
                size += len(chunk)
                if size > max_size:
                    raise HTTPException(
                        status_code=413, 
                        detail=f"File too large. Maximum allowed size is {max_size / (1024*1024):.1f}MB"
                    )
                
                buffer.write(chunk)
    except Exception as e:
        if tmp_path.exists():
            tmp_path.unlink()
        if isinstance(e, HTTPException):
            raise e
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during upload")
    
    return tmp_path
