"""
Voice streaming WebSocket routes.
Refactored to use VoiceService.
"""
import logging
import asyncio
import time
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse
from services.voice.voice_service import voice_service

logger = logging.getLogger("signglove.voice_routes")
router = APIRouter(prefix="/api/voice", tags=["Voice"])

@router.websocket("/voice")
async def websocket_voice_stream(websocket: WebSocket):
    await websocket.accept()
    session_id = voice_service.create_session(websocket)
    logger.info(f"Voice WebSocket connected: {session_id}")
    
    await websocket.send_json({
        "type": "connection_established",
        "session_id": session_id,
        "timestamp": time.time()
    })
    
    try:
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_json(), timeout=30.0)
                if data.get("type") == "voice_data":
                    result = await voice_service.handle_audio_data(
                        session_id, 
                        data.get("audio_data", []), 
                        data.get("sample_rate", 16000),
                        data.get("volume", 0)
                    )
                    if result:
                        await websocket.send_json(result)
                elif data.get("type") == "ping":
                    await websocket.send_json({"type": "pong", "timestamp": time.time()})
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "keepalive", "timestamp": time.time()})
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        voice_service.remove_session(session_id)

@router.get("/status")
async def get_voice_status():
    return JSONResponse(voice_service.get_status())

@router.post("/start")
async def start_voice_session():
    session_id = voice_service.create_session(session_type="http")
    return JSONResponse({"status": "success", "session_id": session_id})

@router.post("/stop")
async def stop_voice_session(session_id: str):
    voice_service.remove_session(session_id)
    return JSONResponse({"status": "success", "message": f"Session {session_id} stopped"})

@router.get("/health")
async def voice_health():
    status = voice_service.get_status()
    return {
        "status": "healthy",
        "voice_recognition_available": status["voice_recognition_enabled"]
    }
