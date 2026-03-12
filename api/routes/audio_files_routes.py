from fastapi import APIRouter, UploadFile, File, HTTPException, status, Response, Depends
from fastapi.responses import FileResponse
from core.settings import settings
from core.database import db
import os
from datetime import datetime
from typing import List
import shutil
import requests
import pygame
import threading
import asyncio
from routes.auth_routes import role_required_dep

router = APIRouter(prefix="/audio-files", tags=["Audio Files"])
AUDIO_DIR = os.path.join(os.path.dirname(__file__), '..', 'audio_files')
if not os.path.exists(AUDIO_DIR):
    os.makedirs(AUDIO_DIR)

# Pydantic models
from pydantic import BaseModel
class AudioFileMeta(BaseModel):
    filename: str
    upload_time: datetime
    uploader: str = "unknown"

MAX_AUDIO_FILE_SIZE_MB = 5
MAX_AUDIO_FILE_SIZE = MAX_AUDIO_FILE_SIZE_MB * 1024 * 1024

# Initialize pygame mixer for laptop audio playback
try:
    pygame.mixer.init()
    PYGAME_AVAILABLE = True
except Exception as e:
    print(f"Warning: pygame not available for audio playback: {e}")
    PYGAME_AVAILABLE = False

@router.get("/", response_model=List[AudioFileMeta])
async def list_audio_files():
    files = await db["audio_files"].find({}).to_list(100)
    return [AudioFileMeta(**f) for f in files]

@router.post("/", status_code=201)
async def upload_audio_file(
    file: UploadFile = File(...),
    uploader: str = "unknown",
    _user=Depends(role_required_dep("editor"))
):
    """
    Upload a new audio file. Reject if file size exceeds MAX_AUDIO_FILE_SIZE_MB.
    """
    filename = file.filename
    # Read file into memory to check size
    contents = await file.read()
    if len(contents) > MAX_AUDIO_FILE_SIZE:
        raise HTTPException(status_code=413, detail=f"File too large (max {MAX_AUDIO_FILE_SIZE_MB}MB)")
    save_path = os.path.join(AUDIO_DIR, filename)
    if os.path.exists(save_path):
        raise HTTPException(status_code=409, detail="File already exists")
    with open(save_path, "wb") as f:
        f.write(contents)
    meta = {
        "filename": filename,
        "upload_time": datetime.utcnow(),
        "uploader": uploader
    }
    await db["audio_files"].insert_one(meta)
    return {"status": "uploaded", "filename": filename}

@router.delete("/{filename}")
async def delete_audio_file(filename: str, _user=Depends(role_required_dep("editor"))):
    save_path = os.path.join(AUDIO_DIR, filename)
    if not os.path.exists(save_path):
        raise HTTPException(status_code=404, detail="File not found")
    os.remove(save_path)
    await db["audio_files"].delete_one({"filename": filename})
    return {"status": "deleted", "filename": filename}

@router.get("/{filename}")
async def get_audio_file(filename: str):
    save_path = os.path.join(AUDIO_DIR, filename)
    if not os.path.exists(save_path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(save_path, media_type="audio/mpeg", filename=filename)

@router.post("/{filename}/play")
async def play_audio_file(filename: str):
    save_path = os.path.join(AUDIO_DIR, filename)
    if not os.path.exists(save_path):
        raise HTTPException(status_code=404, detail="File not found")
    # Send to ESP32
    try:
        with open(save_path, "rb") as f:
            files = {"file": (filename, f, "audio/mpeg")}
            url = f"http://{settings.ESP32_IP}/play_audio"
            resp = requests.post(url, files=files, timeout=5)
        return {"status": "sent", "esp32_status": resp.status_code, "esp32_response": resp.text}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to send audio to ESP32: {e}")

@router.post("/{filename}/play-laptop")
async def play_audio_on_laptop(filename: str):
    """Play audio file directly on the laptop using pygame"""
    if not PYGAME_AVAILABLE:
        raise HTTPException(status_code=503, detail="Audio playback not available - pygame not installed")
    
    save_path = os.path.join(AUDIO_DIR, filename)
    if not os.path.exists(save_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        # Play audio in a separate thread to avoid blocking
        def play_audio():
            try:
                pygame.mixer.music.load(save_path)
                pygame.mixer.music.play()
                # Wait for playback to finish
                while pygame.mixer.music.get_busy():
                    pygame.time.wait(100)
            except Exception as e:
                print(f"Error playing audio: {e}")
        
        # Start playback in background thread
        audio_thread = threading.Thread(target=play_audio)
        audio_thread.daemon = True
        audio_thread.start()
        
        return {"status": "playing", "filename": filename, "location": "laptop"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to play audio on laptop: {e}")

# ESP32 error log endpoint
@router.get("/esp32/error-log")
async def get_esp32_error_log():
    log_path = os.path.join(AUDIO_DIR, "../error.log")
    if not os.path.exists(log_path):
        raise HTTPException(status_code=404, detail="No error log found")
    return FileResponse(log_path, media_type="text/plain", filename="error.log") 