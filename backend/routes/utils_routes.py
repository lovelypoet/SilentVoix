"""
API routes for utility operations in the sign glove system.

Endpoints:
- GET /utils/health: Health check for the API.
- GET /utils/db/stats: Get database statistics.
- DELETE /utils/sensor-data: Delete sensor data before a given timestamp.
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from datetime import datetime
from core.database import db
from core.settings import settings
import requests
from services.tts_service import tts_service, IDLE_GESTURES
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os
from utils.cache import cacheable
from typing import Dict, Any
from core.auth import get_current_user

router = APIRouter(prefix="/utils", tags=["Utilities"])

class TTSRequest(BaseModel):
    text: str

@router.get(
    "/health",
    summary="Health check",
    description="Health check endpoint to verify the API is running."
)
async def health_check() -> Dict[str, Any]:
    """
    Example response:
    {"status": "ok", "message": "Sign Glove API is running"}
    """
    return {"status": "ok", "message": "Sign Glove API is running"}

@router.get(
    "/db/stats",
    summary="Database statistics",
    description="Get statistics for all main collections in the database."
)
@cacheable(ttl=30)
async def db_stats() -> Dict[str, Any]:
    """
    Example response:
    {
        "sensor_data_count": 123,
        "gesture_count": 45,
        "model_results_count": 10,
        "training_sessions_count": 8
    }
    """
    sensor_count = await db["sensor_data"].count_documents({})
    gesture_count = await db["gestures"].count_documents({})
    model_count = await db["model_results"].count_documents({})
    training_sessions = await db["training_sessions"].count_documents({})
    return {
        "sensor_data_count": sensor_count,
        "gesture_count": gesture_count,
        "model_results_count": model_count,
        "training_sessions_count": training_sessions,
    }

@router.delete("/sensor-data")
async def delete_old_sensor_data(before: datetime = Query(..., description="Delete data before this timestamp (UTC)")):
    """
    Delete sensor data with a timestamp older than the specified value.
    """
    result = await db["sensor_data"].delete_many({"timestamp": {"$lt": before}})
    return {"deleted_count": result.deleted_count}

@router.post("/test_tts_to_esp32")
async def test_tts_to_esp32(req: TTSRequest):
    """
    Generate TTS audio for the given text and send it to the ESP32 for playback.
    """
    try:
        tts_result = await tts_service.speak(req.text)
        audio_path = tts_result.get("audio_path")
        if not audio_path or not os.path.exists(audio_path):
            raise HTTPException(status_code=500, detail="TTS audio file not found.")
        with open(audio_path, "rb") as f:
            files = {"file": ("audio.mp3", f, "audio/mpeg")}
            try:
                url = f"http://{settings.ESP32_IP}/play_audio"
                response = requests.post(url, files=files, timeout=5)
                return {
                    "status": "sent",
                    "esp32_status": response.status_code,
                    "esp32_response": response.text
                }
            except Exception as e:
                raise HTTPException(status_code=502, detail=f"Failed to send audio to ESP32: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS or send error: {e}")

@router.get("/training/logs")
async def get_training_logs(lines: int = Query(200, ge=1, le=2000)):
    """
    Return the last N lines of the training log so clients can display epoch/progress.
    """
    path = settings.TRAINING_LOG_PATH
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Training log not found")
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.readlines()
        tail = content[-lines:]
        return {"status": "success", "lines": tail}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read training log: {e}")

@router.get("/tts/config")
async def get_tts_config(current_user: dict = Depends(get_current_user)):
    """Get current TTS configuration and gesture mapping."""
    try:
        config = tts_service.get_config()
        config["available_languages"] = tts_service.get_available_languages()
        config["current_language"] = tts_service.current_language
        config["idle_gestures"] = IDLE_GESTURES
        config["filter_idle_gestures"] = settings.TTS_FILTER_IDLE_GESTURES
        return {"status": "success", "data": config}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get TTS config: {str(e)}")

@router.post("/tts/language")
async def set_tts_language(
    language: str,
    current_user: dict = Depends(get_current_user)
):
    """Set the current language for TTS."""
    try:
        success = tts_service.set_language(language)
        if success:
            return {
                "status": "success", 
                "message": f"Language set to {language}",
                "current_language": tts_service.current_language
            }
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported language: {language}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to set language: {str(e)}")

@router.get("/tts/languages")
async def get_available_languages(current_user: dict = Depends(get_current_user)):
    """Get list of available languages."""
    try:
        languages = tts_service.get_available_languages()
        return {"status": "success", "languages": languages}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get languages: {str(e)}")

@router.post("/tts/gesture-mapping")
async def update_gesture_mapping(
    mapping: Dict[str, str],
    language: str = "en",
    current_user: dict = Depends(get_current_user)
):
    """Update gesture mapping for TTS in a specific language."""
    try:
        # This would need to be implemented to update the global LANGUAGE_MAPPINGS
        # For now, return a message about the limitation
        return {
            "status": "info", 
            "message": "Gesture mapping updates require service restart. Use tts_config.json for configuration.",
            "current_language": language,
            "note": "Update tts_config.json and restart service to change mappings"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update gesture mapping: {str(e)}")

@router.post("/tts/test")
async def test_tts(
    text: str,
    current_user: dict = Depends(get_current_user)
):
    """Test TTS with given text."""
    try:
        result = await tts_service.speak(text)
        return {"status": "success", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS test failed: {str(e)}")

@router.post("/tts/test-gesture")
async def test_gesture_tts(
    gesture_label: str,
    language: str = "en",
    current_user: dict = Depends(get_current_user)
):
    """Test TTS for a specific gesture label in specified language."""
    try:
        result = await tts_service.speak_gesture(gesture_label, language=language)
        return {"status": "success", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gesture TTS test failed: {str(e)}")

@router.post("/tts/test-multilingual")
async def test_multilingual_tts(
    gesture_label: str,
    current_user: dict = Depends(get_current_user)
):
    """Test TTS for a gesture in all available languages."""
    try:
        results = {}
        for language in tts_service.get_available_languages():
            result = await tts_service.speak_gesture(gesture_label, language=language)
            results[language] = result
        return {"status": "success", "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Multilingual TTS test failed: {str(e)}")

# ESP32 + SD Card Integration Endpoints
@router.get("/esp32/tts-info/{gesture_label}")
async def get_esp32_tts_info(
    gesture_label: str,
    language: str = "en",
    current_user: dict = Depends(get_current_user)
):
    """Get ESP32 TTS file information for a gesture (for SD card playback)."""
    try:
        result = await tts_service.get_esp32_tts_info(gesture_label, language=language)
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get ESP32 TTS info: {str(e)}")

@router.get("/esp32/tts-files")
async def get_esp32_tts_files(
    language: str = "en",
    current_user: dict = Depends(get_current_user)
):
    """Get all available TTS files for ESP32 SD card in a specific language."""
    try:
        files = []
        for gesture_label in tts_service.LANGUAGE_MAPPINGS.get(language, {}).keys():
            if tts_service.should_speak_gesture(gesture_label):
                file_info = await tts_service.get_esp32_tts_info(gesture_label, language)
                if file_info["status"] == "success":
                    files.append(file_info["data"])
        
        return {
            "status": "success",
            "language": language,
            "total_files": len(files),
            "files": files
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get ESP32 TTS files: {str(e)}")

@router.get("/esp32/sd-structure")
async def get_esp32_sd_structure(current_user: dict = Depends(get_current_user)):
    """Get the recommended SD card folder structure for ESP32 TTS files."""
    try:
        structure = {
            "sd_root": "/sd",
            "tts_folder": "/sd/tts",
            "languages": {}
        }
        
        for lang in tts_service.get_available_languages():
            structure["languages"][lang] = {
                "path": f"/sd/tts/{lang}",
                "files": []
            }
            
            for gesture_label in tts_service.LANGUAGE_MAPPINGS.get(lang, {}).keys():
                if tts_service.should_speak_gesture(gesture_label):
                    filename = tts_service.ESP32_TTS_FILENAMES.get(gesture_label, f"{gesture_label.lower()}.mp3")
                    structure["languages"][lang]["files"].append(filename)
        
        return {"status": "success", "sd_structure": structure}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get SD structure: {str(e)}")

@router.post("/esp32/generate-tts-files")
async def generate_esp32_tts_files(
    language: str = "en",
    current_user: dict = Depends(get_current_user)
):
    """Generate TTS audio files for ESP32 SD card in specified language."""
    try:
        generated_files = []
        failed_files = []
        
        for gesture_label in tts_service.LANGUAGE_MAPPINGS.get(language, {}).keys():
            if tts_service.should_speak_gesture(gesture_label):
                try:
                    # Generate TTS audio file
                    text = tts_service.get_gesture_text(gesture_label, language)
                    result = await tts_service.speak(text)
                    
                    if result["status"] == "success":
                        generated_files.append({
                            "gesture": gesture_label,
                            "text": text,
                            "audio_file": result.get("audio_path", "generated"),
                            "esp32_path": tts_service.get_esp32_tts_path(gesture_label, language)
                        })
                    else:
                        failed_files.append({
                            "gesture": gesture_label,
                            "error": result.get("message", "Unknown error")
                        })
                except Exception as e:
                    failed_files.append({
                        "gesture": gesture_label,
                        "error": str(e)
                    })
        
        return {
            "status": "success",
            "language": language,
            "generated_files": generated_files,
            "failed_files": failed_files,
            "total_generated": len(generated_files),
            "total_failed": len(failed_files)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate TTS files: {str(e)}")

@router.get("/esp32/tts-status")
async def get_esp32_tts_status(current_user: dict = Depends(get_current_user)):
    """Get overall ESP32 TTS system status and statistics."""
    try:
        status = {
            "total_languages": len(tts_service.get_available_languages()),
            "current_language": tts_service.current_language,
            "total_gestures": len(tts_service.LANGUAGE_MAPPINGS.get("en", {})),
            "meaningful_gestures": 0,
            "idle_gestures": 0,
            "tts_enabled": settings.TTS_ENABLED,
            "filter_enabled": settings.TTS_FILTER_IDLE_GESTURES
        }
        
        # Count meaningful vs idle gestures
        for gesture_label in tts_service.LANGUAGE_MAPPINGS.get("en", {}).keys():
            if tts_service.should_speak_gesture(gesture_label):
                status["meaningful_gestures"] += 1
            else:
                status["idle_gestures"] += 1
        
        return {"status": "success", "data": status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get TTS status: {str(e)}")
