import logging
import time
import asyncio
import numpy as np
import warnings
from datetime import datetime
from typing import Dict, Set, Optional, Any, List
from fastapi import WebSocket, HTTPException

from api.core.database import voice_collection

# Voice recognition imports (optional)
try:
    import speech_recognition as sr
    HAS_SPEECH_RECOGNITION = True
except ImportError:
    HAS_SPEECH_RECOGNITION = False

try:
    import whisper
    HAS_WHISPER = True
except ImportError:
    HAS_WHISPER = False

logger = logging.getLogger("signglove.voice_service")

class VoiceProcessor:
    def __init__(self):
        self.recognizer = None
        self.whisper_model = None
        
        if HAS_SPEECH_RECOGNITION:
            self.recognizer = sr.Recognizer()
            
        if HAS_WHISPER:
            try:
                self.whisper_model = whisper.load_model("base")
                logger.info("Whisper model loaded successfully")
            except Exception as e:
                logger.warning(f"Failed to load Whisper model: {e}")
                self.whisper_model = None
    
    async def process_audio_chunk(self, audio_data: list, sample_rate: int = 16000) -> dict:
        """Process audio chunk for voice recognition"""
        try:
            if not audio_data:
                return {"type": "voice_analysis", "volume": 0.0, "has_speech": False, "error": "Empty data"}
                
            audio_np = np.array(audio_data, dtype=np.float32)
            audio_np = audio_np.astype(np.float32) / 32768.0
            rms = np.sqrt(np.maximum(np.mean(np.square(audio_np)), 1e-10))
            volume = float(rms)
            
            result = {
                "type": "voice_analysis",
                "volume": volume,
                "has_speech": bool(volume > 0.01),
                "timestamp": float(time.time())
            }
            
            if result["has_speech"] and (self.recognizer or self.whisper_model):
                audio_bytes = np.int16(audio_np * 32767).tobytes()
                audio_segment = sr.AudioData(audio_bytes, sample_rate, 2)
                
                if self.recognizer:
                    try:
                        text = self.recognizer.recognize_google(audio_segment)
                        result.update({"text": text, "confidence": 0.9, "recognition_service": "google"})
                    except: pass
                
                if "text" not in result and self.whisper_model:
                    try:
                        res = self.whisper_model.transcribe(audio_np.astype(np.float32))
                        if res and "text" in res:
                            result.update({"text": str(res["text"]).strip(), "confidence": 0.8, "recognition_service": "whisper"})
                    except Exception as e:
                        logger.warning(f"Whisper error: {e}")
            return result
        except Exception as e:
            logger.error(f"process_audio_chunk error: {e}")
            return {"type": "error", "error": str(e)}

class VoiceService:
    def __init__(self):
        self.processor = VoiceProcessor()
        self.active_connections: Set[WebSocket] = set()
        self.sessions: Dict[str, dict] = {}
        self.total_sessions = 0
        self.last_activity = None

    def create_session(self, websocket: Optional[WebSocket] = None, session_type: str = "websocket") -> str:
        session_id = f"{session_type}_{int(time.time())}_{len(self.sessions)}"
        self.sessions[session_id] = {
            "start_time": time.time(),
            "audio_chunks_received": 0,
            "total_audio_duration": 0,
            "websocket": websocket,
            "type": session_type,
            "status": "active"
        }
        self.total_sessions += 1
        self.last_activity = datetime.utcnow().isoformat()
        if websocket:
            self.active_connections.add(websocket)
        return session_id

    def remove_session(self, session_id: str):
        if session_id in self.sessions:
            ws = self.sessions[session_id].get("websocket")
            if ws:
                self.active_connections.discard(ws)
            del self.sessions[session_id]

    async def handle_audio_data(self, session_id: str, audio_data: list, sample_rate: int, volume: float = 0):
        if session_id not in self.sessions: return None
        
        session = self.sessions[session_id]
        session["audio_chunks_received"] += 1
        chunk_dur = len(audio_data) / sample_rate
        session["total_audio_duration"] += chunk_dur
        self.last_activity = datetime.utcnow().isoformat()

        result = await self.processor.process_audio_chunk(audio_data, sample_rate)
        result.update({"chunk_id": session["audio_chunks_received"], "session_id": session_id})

        if result.get("has_speech"):
            try:
                await voice_collection.insert_one({
                    "session_id": session_id,
                    "timestamp": datetime.utcnow(),
                    "volume": volume or result.get("volume", 0),
                    "audio_duration": chunk_dur,
                    "recognition_result": result.get("text", ""),
                    "confidence": result.get("confidence", 0.0)
                })
            except: pass
        return result

    def get_status(self) -> dict:
        return {
            "status": "active" if self.active_connections else "inactive",
            "active_connections": len(self.active_connections),
            "total_sessions": self.total_sessions,
            "last_activity": self.last_activity,
            "voice_recognition_enabled": HAS_SPEECH_RECOGNITION or HAS_WHISPER,
            "available_engines": {"speech_recognition": HAS_SPEECH_RECOGNITION, "whisper": HAS_WHISPER},
            "session_details": [
                {
                    "session_id": sid,
                    "duration": time.time() - s["start_time"],
                    "chunks_received": s["audio_chunks_received"],
                    "total_duration": s["total_audio_duration"]
                } for sid, s in self.sessions.items()
            ]
        }

voice_service = VoiceService()
