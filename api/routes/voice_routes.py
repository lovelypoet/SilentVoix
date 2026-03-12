"""
Voice streaming WebSocket routes for real-time voice recognition and processing.

Endpoints:
- WebSocket /ws/voice: Real-time voice data streaming and recognition
- GET /voice/status: Voice connection status
- POST /voice/start: Start voice streaming session
- POST /voice/stop: Stop voice streaming session
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import JSONResponse
import logging
import json
import asyncio
import time
from typing import Dict, Set
from datetime import datetime
import numpy as np
import warnings
warnings.filterwarnings("ignore", message="FP16 is not supported on CPU; using FP32 instead")

# Voice recognition imports (optional - install as needed)
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

from core.database import voice_collection
try:
    from services.tts_service import tts_service
except ImportError:
    tts_service = None

# Initialize logger early
logger = logging.getLogger("signglove")

# Create the main router
router = APIRouter(prefix="/api/voice", tags=["Voice"])

# Voice streaming state management
active_connections: Set[WebSocket] = set()
voice_sessions: Dict[str, dict] = {}
connection_status = {
    "active_connections": 0,
    "total_sessions": 0,
    "last_activity": None,
    "voice_recognition_enabled": HAS_SPEECH_RECOGNITION or HAS_WHISPER
}

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
            # Convert audio data to numpy array and ensure it's not empty
            if not audio_data or len(audio_data) == 0:
                return {
                    "type": "voice_analysis",
                    "volume": 0.0,
                    "has_speech": False,
                    "timestamp": time.time(),
                    "error": "Empty audio data"
                }
                
            audio_np = np.array(audio_data, dtype=np.float32)
            
            # Calculate RMS volume with safety checks
            try:
                # Convert to float32 and normalize
                audio_np = audio_np.astype(np.float32) / 32768.0  # For 16-bit audio
                # Calculate RMS with epsilon to avoid sqrt of zero/negative
                rms = np.sqrt(np.maximum(np.mean(np.square(audio_np)), 1e-10))
                volume = float(rms)
            except (ValueError, FloatingPointError) as e:
                logger.warning(f"Volume calculation error: {e}")
                volume = 0.0
            
            # Create result with proper JSON-serializable types
            result = {
                "type": "voice_analysis",
                "volume": volume,
                "has_speech": bool(volume > 0.01),  # Adjust threshold as needed
                "timestamp": float(time.time())
            }
            
            # If we have speech recognition available and detect speech
            if result.get("has_speech", False) and (self.recognizer or self.whisper_model):
                try:
                    # Convert to audio format for recognition
                    audio_bytes = np.int16(audio_np * 32767).tobytes()
                    audio_segment = sr.AudioData(
                        audio_bytes,
                        sample_rate=sample_rate,
                        sample_width=2  # 16-bit
                    )
                    
                    # Try speech recognition if available
                    if self.recognizer:
                        try:
                            text = self.recognizer.recognize_google(audio_segment)
                            result.update({
                                "text": text,
                                "confidence": 0.9,  # Default confidence
                                "recognition_service": "google"
                            })
                        except sr.UnknownValueError:
                            pass  # No speech detected
                        except Exception as e:
                            logger.warning(f"Speech recognition error: {e}")
                    
                    # Fall back to Whisper if available and no result from Google
                    if "text" not in result and self.whisper_model:
                        try:
                            # Convert to float32 numpy array in range [-1, 1]
                            audio_np_whisper = audio_np.astype(np.float32)
                            # Resample to 16kHz if needed (Whisper's expected sample rate)
                            if sample_rate != 16000:
                                import librosa
                                with warnings.catch_warnings():
                                    warnings.simplefilter("ignore")
                                    audio_np_whisper = librosa.resample(
                                        audio_np_whisper, 
                                        orig_sr=sample_rate, 
                                        target_sr=16000
                                    )
                            # Run inference with error handling
                            try:
                                result_whisper = self.whisper_model.transcribe(audio_np_whisper)
                                if result_whisper and "text" in result_whisper:
                                    result.update({
                                        "text": str(result_whisper["text"]).strip(),
                                        "confidence": float(result_whisper.get("confidence", 0.8)),
                                        "recognition_service": "whisper"
                                    })
                            except Exception as whisper_error:
                                logger.warning(f"Whisper transcription error: {whisper_error}")
                                
                        except Exception as e:
                            logger.warning(f"Whisper processing error: {e}")
                            
                except Exception as e:
                    logger.error(f"Audio processing error: {e}")
                    result["error"] = str(e)
            
            return result
            
        except Exception as e:
            logger.error(f"Error in process_audio_chunk: {e}")
            return {
                "type": "error",
                "error": str(e),
                "timestamp": float(time.time())
            }
    
voice_processor = VoiceProcessor()

@router.websocket("/voice")
async def websocket_voice_stream(websocket: WebSocket):
    """
    WebSocket endpoint for real-time voice streaming and recognition.
    Receives audio data and returns voice recognition results.
    """
    await websocket.accept()
    session_id = f"voice_{int(time.time())}"
    
    # Add to active connections
    active_connections.add(websocket)
    connection_status["active_connections"] = len(active_connections)
    connection_status["last_activity"] = datetime.utcnow().isoformat()
    
    # Create session
    voice_sessions[session_id] = {
        "start_time": time.time(),
        "audio_chunks_received": 0,
        "total_audio_duration": 0,
        "websocket": websocket
    }
    connection_status["total_sessions"] += 1
    
    logger.info(f"Voice WebSocket connected: {session_id}")
    
    # Send welcome message
    await websocket.send_json({
        "type": "connection_established",
        "session_id": session_id,
        "voice_recognition_available": bool(HAS_SPEECH_RECOGNITION or HAS_WHISPER),
        "timestamp": time.time()
    })
    
    try:
        while True:
            try:
                # Receive audio data with timeout
                data = await asyncio.wait_for(websocket.receive_json(), timeout=30.0)
                connection_status["last_activity"] = datetime.utcnow().isoformat()
                
                if data.get("type") == "voice_data":
                    # Process audio chunk
                    audio_data = data.get("audio_data", [])
                    sample_rate = data.get("sample_rate", 16000)
                    volume = data.get("volume", 0)
                    
                    # Validate audio data
                    if not isinstance(audio_data, list) or len(audio_data) == 0:
                        logger.warning("Received empty or invalid audio data")
                        await websocket.send_json({
                            "type": "error",
                            "message": "Empty or invalid audio data",
                            "timestamp": time.time()
                        })
                        continue
                    
                    # Update session stats
                    voice_sessions[session_id]["audio_chunks_received"] += 1
                    chunk_duration = len(audio_data) / sample_rate
                    voice_sessions[session_id]["total_audio_duration"] += chunk_duration
                    
                    try:
                        # Process audio for voice recognition
                        result = await voice_processor.process_audio_chunk(audio_data, sample_rate)
                        
                        # Ensure result is a dictionary
                        if not isinstance(result, dict):
                            result = {"type": "error", "message": "Invalid result from processor"}
                        
                        # Add metadata
                        result.update({
                            "chunk_id": voice_sessions[session_id]["audio_chunks_received"],
                            "session_id": session_id,
                            "timestamp": time.time()
                        })
                        
                        # Store in database if significant
                        if result.get("has_speech", False):
                            try:
                                voice_doc = {
                                    "session_id": session_id,
                                    "timestamp": datetime.utcnow(),
                                    "volume": volume,
                                    "audio_duration": chunk_duration,
                                    "has_speech": True,
                                    "recognition_result": result.get("text", ""),
                                    "confidence": result.get("confidence", 0.0)
                                }
                                await voice_collection.insert_one(voice_doc)
                            except Exception as e:
                                logger.warning(f"Failed to store voice data: {e}")
                        
                        # Send result back to client with audio data for playback
                        try:
                            response = {
                                **result,
                                "chunk_id": voice_sessions[session_id]["audio_chunks_received"],
                                "session_id": session_id,
                                "timestamp": time.time(),
                                # Include the original audio data for playback
                                "audio_data": audio_data,
                                "sample_rate": sample_rate
                            }
                            await websocket.send_json(response)
                            logger.debug(f"Sent result for chunk {response.get('chunk_id')}")
                        except Exception as e:
                            logger.error(f"Failed to send result: {e}")
                            break
                            
                    except Exception as e:
                        logger.error(f"Error processing audio chunk: {e}")
                        await websocket.send_json({
                            "type": "error",
                            "message": f"Error processing audio: {str(e)}",
                            "timestamp": time.time()
                        })
                
                else:
                    # Handle other message types
                    if data.get("type") == "ping":
                        # Respond to ping for connection health check
                        await websocket.send_json({
                            "type": "pong",
                            "timestamp": time.time()
                        })
                    else:
                        await websocket.send_json({
                            "type": "error",
                            "message": f"Unsupported message type: {data.get('type')}",
                            "timestamp": time.time()
                        })
                    
            except asyncio.TimeoutError:
                # Send keepalive
                await websocket.send_json({"type": "keepalive", "timestamp": time.time()})
                continue
                
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}")
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON format",
                    "timestamp": time.time()
                })
                continue
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        # Clean up
        active_connections.discard(websocket)
        connection_status["active_connections"] = len(active_connections)
        if session_id in voice_sessions:
            voice_sessions[session_id]["end_time"] = time.time()
            voice_sessions[session_id]["status"] = "disconnected"
        logger.info(f"Voice session ended: {session_id}")

@router.get("/status")
async def get_voice_status():
    """Get current voice streaming status and connection information"""
    return JSONResponse({
        "status": "active" if connection_status["active_connections"] > 0 else "inactive",
        "active_connections": connection_status["active_connections"],
        "total_sessions": connection_status["total_sessions"],
        "last_activity": connection_status["last_activity"],
        "voice_recognition_enabled": connection_status["voice_recognition_enabled"],
        "available_engines": {
            "speech_recognition": HAS_SPEECH_RECOGNITION,
            "whisper": HAS_WHISPER
        },
        "session_details": [
            {
                "session_id": sid,
                "duration": time.time() - session["start_time"],
                "chunks_received": session["audio_chunks_received"],
                "total_duration": session["total_audio_duration"]
            }
            for sid, session in voice_sessions.items()
        ]
    })

@router.post("/start")
async def start_voice_session():
    """Start a new voice streaming session (HTTP endpoint)"""
    session_id = f"http_voice_{int(time.time())}"
    
    voice_sessions[session_id] = {
        "start_time": time.time(),
        "audio_chunks_received": 0,
        "total_audio_duration": 0,
        "type": "http"
    }
    
    connection_status["total_sessions"] += 1
    connection_status["last_activity"] = datetime.utcnow().isoformat()
    
    return JSONResponse({
        "status": "success",
        "session_id": session_id,
        "message": "Voice session started",
        "websocket_url": "/voice"
    })

@router.post("/stop")
async def stop_voice_session(session_id: str = None):
    """Stop a voice streaming session"""
    if session_id and session_id in voice_sessions:
        session = voice_sessions[session_id]
        duration = time.time() - session["start_time"]
        
        del voice_sessions[session_id]
        
        return JSONResponse({
            "status": "success",
            "message": f"Voice session {session_id} stopped",
            "session_duration": duration,
            "chunks_processed": session.get("audio_chunks_received", 0)
        })
    else:
        return JSONResponse({
            "status": "error",
            "message": "Session not found or no session specified"
        }, status_code=404)

@router.get("/health")
async def voice_health_check():
    """Health check endpoint for voice streaming system"""
    return JSONResponse({
        "status": "healthy",
        "voice_system": "operational",
        "active_connections": len(active_connections),
        "voice_recognition_available": HAS_SPEECH_RECOGNITION or HAS_WHISPER,
        "timestamp": datetime.utcnow().isoformat()
    })

@router.get("/sessions")
async def list_voice_sessions():
    """List all active voice sessions"""
    sessions = []
    for session_id, session in voice_sessions.items():
        sessions.append({
            "session_id": session_id,
            "start_time": session["start_time"],
            "duration": time.time() - session["start_time"],
            "audio_chunks_received": session.get("audio_chunks_received", 0),
            "total_audio_duration": session.get("total_audio_duration", 0),
            "type": session.get("type", "websocket")
        })
    
    return JSONResponse({
        "active_sessions": len(sessions),
        "sessions": sessions
    })

@router.post("/manual")
async def process_manual_voice():
    """
    Endpoint to process manual voice input, return recognized text, and play the audio
    """
    try:
        if not HAS_SPEECH_RECOGNITION:
            raise HTTPException(
                status_code=501, 
                detail="Speech recognition not available. Install SpeechRecognition and PyAudio."
            )
            
        recognizer = sr.Recognizer()
        
        try:
            # List available microphones for debugging
            mic_list = sr.Microphone.list_microphone_names()
            logger.info("Available microphones:")
            for index, name in enumerate(mic_list):
                logger.info(f"  {index}: {name}")
            
            # Try to find the best microphone
            mic_index = next((i for i, name in enumerate(mic_list) 
                           if 'microphone' in name.lower() or 'mic' in name.lower() or 'realtek' in name.lower()), 0)
            
            logger.info(f"Using microphone: {mic_list[mic_index]} (index: {mic_index})")
            
            with sr.Microphone(device_index=mic_index) as source:
                # Adjust for ambient noise with a longer duration
                logger.info("Adjusting for ambient noise (2 seconds)...")
                recognizer.energy_threshold = 4000
                recognizer.dynamic_energy_threshold = True
                recognizer.pause_threshold = 0.8
                recognizer.phrase_threshold = 0.3
                recognizer.non_speaking_duration = 0.5
                
                recognizer.adjust_for_ambient_noise(source, duration=2)
                logger.info("Listening for voice input (5 second timeout)...")
                
                try:
                    # Listen with longer timeout and phrase time
                    audio = recognizer.listen(source, timeout=5, phrase_time_limit=7)
                    logger.info("Processing voice input...")
                    
                    # Save audio to file for debugging
                    import os
                    os.makedirs("debug_audio", exist_ok=True)
                    debug_file = f"debug_audio/audio_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.wav"
                    with open(debug_file, "wb") as f:
                        f.write(audio.get_wav_data())
                    logger.info(f"Saved audio to {debug_file}")
                    
                    # Play the audio on the laptop's speakers
                    try:
                        import sounddevice as sd
                        import soundfile as sf
                        import threading
                        
                        def play_audio(file_path):
                            try:
                                # Load the audio file
                                data, samplerate = sf.read(file_path, dtype='float32')
                                # Play the audio
                                sd.play(data, samplerate)
                                sd.wait()  # Wait until audio is finished playing
                                logger.info(f"Finished playing audio: {file_path}")
                            except Exception as e:
                                logger.error(f"Error playing audio: {e}")
                        
                        # Play audio in a separate thread to not block the response
                        audio_thread = threading.Thread(
                            target=play_audio, 
                            args=(debug_file,),
                            daemon=True
                        )
                        audio_thread.start()
                        
                    except ImportError as e:
                        logger.warning(f"Audio playback libraries not installed. Install with: pip install sounddevice soundfile. Error: {e}")
                    except Exception as e:
                        logger.error(f"Error setting up audio playback: {e}")
                    
                    # Try Google's speech recognition with explicit language
                    try:
                        text = recognizer.recognize_google(
                            audio,
                            language="en-US",  # Force English (United States)
                            show_all=False  # Only return the most likely result
                        )
                        
                        if not text or not text.strip():
                            raise sr.UnknownValueError("No speech detected in audio")
                            
                        logger.info(f"Recognized text: {text}")
                        
                        # Return the recognized text and audio file path
                        return {
                            "status": "success",
                            "text": text,
                            "audio_file": debug_file
                        }
                        
                    except sr.UnknownValueError:
                        logger.warning("Google Speech Recognition could not understand audio")
                        return {"status": "error", "message": "Could not understand audio"}
                        
                    except sr.RequestError as e:
                        logger.error(f"Could not request results from Google Speech Recognition service: {e}")
                        return {"status": "error", "message": "Speech service unavailable"}
                        
                except sr.WaitTimeoutError:
                    logger.warning("No speech detected within timeout")
                    return {"status": "error", "message": "No speech detected"}
                    
        except OSError as e:
            logger.error(f"Microphone access error: {e}")
            return {"status": "error", "message": "Microphone access error"}
            
    except Exception as e:
        logger.error(f"Voice recognition error: {e}", exc_info=True)
        return {"status": "error", "message": "Voice recognition failed"}

@router.get("/health")
async def voice_health():
    """Health check for voice module"""
    return {
        "status": "ok",
        "speech_recognition_available": HAS_SPEECH_RECOGNITION,
        "whisper_available": HAS_WHISPER
    }
