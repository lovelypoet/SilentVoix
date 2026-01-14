"""
    TTS Service
"""
import asyncio
import os
import logging
import hashlib
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, Optional
from core.settings import settings
import pygame
import threading
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

# TTS Libraries Import Check
try:
    import pyttsx3
    HAS_PYTTSX3 = True
except ImportError:
    HAS_PYTTSX3 = False
try:
    from gtts import gTTS
    HAS_GTTS = True
except ImportError:
    HAS_GTTS = False
try:
    import edge_tts
    HAS_EDGE_TTS = True
except ImportError:
    HAS_EDGE_TTS = False

# Multi-language gesture mapping for ESP32 + SD card system
LANGUAGE_MAPPINGS = {
    "en": {
        "Class 0": "Hello",
        "Class 1": "Yes", 
        "Class 2": "No",
        "Class 3": "Thank you",
        "Class 4": "Please",
        "Class 5": "Sorry",
        "Class 6": "Goodbye",
        "Class 7": "Help",
        "Class 8": "Water",
        "Class 9": "Food",
        "Class 10": "Emergency",
    },
    "vn": {
        "Class 0": "Xin chào",
        "Class 1": "Có", 
        "Class 2": "Không",
        "Class 3": "Cảm ơn",
        "Class 4": "Làm ơn",
        "Class 5": "Xin lỗi",
        "Class 6": "Tạm biệt",
        "Class 7": "Giúp đỡ",
        "Class 8": "Nước",
        "Class 9": "Thức ăn",
        "Class 10": "Khẩn cấp",
    },
    "fr": {
        "Class 0": "Bonjour",
        "Class 1": "Oui", 
        "Class 2": "Non",
        "Class 3": "Merci",
        "Class 4": "S'il vous plaît",
        "Class 5": "Désolé",
        "Class 6": "Au revoir",
        "Class 7": "Aide",
        "Class 8": "Eau",
        "Class 9": "Nourriture",
        "Class 10": "Urgence",
    }
}

# ESP32 SD Card TTS file paths
ESP32_TTS_PATHS = {
    "en": "/sd/tts/en/",
    "vn": "/sd/tts/vn/", 
    "fr": "/sd/tts/fr/"
}

# ESP32 TTS file naming convention
ESP32_TTS_FILENAMES = {
    "Class 0": "hello.mp3",
    "Class 1": "yes.mp3",
    "Class 2": "no.mp3", 
    "Class 3": "thankyou.mp3",
    "Class 4": "please.mp3",
    "Class 5": "sorry.mp3",
    "Class 6": "goodbye.mp3",
    "Class 7": "help.mp3",
    "Class 8": "water.mp3",
    "Class 9": "food.mp3",
    "Class 10": "emergency.mp3"
}

# Default language
DEFAULT_LANGUAGE = "en"

# Basic/idle gestures that should NOT trigger TTS
IDLE_GESTURES = {
    "hand_resting": ["rest", "idle", "neutral", "relaxed"],
    "basic_movement": ["movement", "wave", "point", "gesture"],
    "no_meaning": ["", "none", "unknown", "undefined"]
}

class TTSService:
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.cache = {}
        self.pyttsx3_engine = None
        self.current_language = DEFAULT_LANGUAGE
        # Ensure cache dir exists
        if settings.TTS_CACHE_ENABLED and not os.path.exists(settings.TTS_CACHE_DIR):
            os.makedirs(settings.TTS_CACHE_DIR)
        if HAS_PYTTSX3:
            self._init_pyttsx3()
        # Initialize pygame for laptop audio playback
        try:
            pygame.mixer.init()
            self.pygame_available = True
        except Exception as e:
            logging.warning(f"pygame not available for audio playback: {e}")
            self.pygame_available = False

    def _init_pyttsx3(self):
        try:
            self.pyttsx3_engine = pyttsx3.init()
            self.pyttsx3_engine.setProperty('rate', settings.TTS_RATE)
            self.pyttsx3_engine.setProperty('volume', settings.TTS_VOLUME)
        except Exception as e:
            logging.error(f"Failed to initialize pyttsx3: {e}")

    def get_cache_path(self, text, voice):
        text_hash = hashlib.md5(f"{text}_{voice}".encode()).hexdigest()
        return os.path.join(settings.TTS_CACHE_DIR, f"{text_hash}.mp3")

    def set_language(self, language: str):
        """Set the current language for TTS."""
        if language in LANGUAGE_MAPPINGS:
            self.current_language = language
            return True
        return False

    def get_available_languages(self):
        """Get list of available languages."""
        return list(LANGUAGE_MAPPINGS.keys())

    def get_gesture_text(self, label: str, language: str = None):
        """Get gesture text in specified language or current language."""
        lang = language or self.current_language
        return LANGUAGE_MAPPINGS.get(lang, {}).get(label, "")

    def get_esp32_tts_path(self, gesture_label: str, language: str = None):
        """Get the ESP32 SD card path for TTS audio file."""
        lang = language or self.current_language
        if lang not in ESP32_TTS_PATHS:
            return None
            
        filename = ESP32_TTS_FILENAMES.get(gesture_label, f"{gesture_label.lower()}.mp3")
        return f"{ESP32_TTS_PATHS[lang]}{filename}"

    def should_speak_gesture(self, label: str) -> bool:
        """
        Determines if a gesture should trigger TTS.
        Returns False for basic/idle gestures that don't convey meaning.
        """
        if not label or label.strip() == "":
            return False
            
        # If filtering is disabled, speak for all gestures
        if not settings.TTS_FILTER_IDLE_GESTURES:
            return True
            
        # Check if it's a meaningful gesture in any language
        for lang, mappings in LANGUAGE_MAPPINGS.items():
            if label in mappings and mappings[label].strip():
                return True
            
        # Check if it's an idle gesture that shouldn't speak
        label_lower = label.lower()
        for idle_types in IDLE_GESTURES.values():
            if any(idle_type in label_lower for idle_type in idle_types):
                return False
                
        # Default: only speak if it's a recognized meaningful gesture
        return any(label in mappings for mappings in LANGUAGE_MAPPINGS.values())

    async def speak(self, text: str, voice: str = None):
        if not settings.TTS_ENABLED:
            return {"status": "disabled"}
        provider = settings.TTS_PROVIDER
        try:
            if provider == "edge" and HAS_EDGE_TTS:
                return await self._speak_edge(text, voice)
            elif provider == "gtts" and HAS_GTTS:
                return await self._speak_gtts(text)
            elif provider == "pyttsx3" and HAS_PYTTSX3:
                return await self._speak_pyttsx3(text)
            else:
                return {"status": "error", "message": "No TTS provider available"}
        except Exception as e:
            logging.error(f"TTS error: {e}")
            return {"status": "error", "message": str(e)}

    async def speak_gesture(self, gesture_label: str, language: str = None, voice: str = None, 
                     play_on_laptop: bool = True, play_on_esp32: bool = True):
        """
        Speaks a gesture on both laptop and ESP32 if configured.
        
        Args:
            gesture_label: The gesture label to speak
            language: Language code (e.g., 'en', 'vn')
            voice: Voice to use (if supported by TTS engine)
            play_on_laptop: Whether to play audio on laptop
            play_on_esp32: Whether to send command to ESP32 to play audio
            
        Returns:
            dict: Status of the operation
        """
        if not self.should_speak_gesture(gesture_label):
            return {
                "status": "skipped",
                "reason": "Gesture does not require TTS"
            }

        language = language or self.current_language
        
        # Get the text to speak in the specified language
        text = self.get_gesture_text(gesture_label, language)
        if not text:
            return {
                "status": "error",
                "message": f"No translation found for gesture '{gesture_label}' in language '{language}'"
            }

        try:
            # Play on laptop if enabled
            laptop_result = None
            if play_on_laptop and self.pygame_available:
                try:
                    # Use the existing speak method which handles caching
                    tts_result = await self.speak(text, voice)
                    if tts_result and tts_result.get('status') == 'success' and 'audio_path' in tts_result:
                        play_result = await self.play_on_laptop(tts_result['audio_path'])
                        laptop_result = play_result.get('status', 'unknown')
                    else:
                        laptop_result = f"error: {tts_result.get('message', 'Unknown error')}"
                except Exception as e:
                    error_msg = str(e)
                    logging.error(f"Error in speak_gesture: {error_msg}")
                    laptop_result = f"error: {error_msg}"
            
            # Get ESP32 info if needed
            esp32_info = None
            if play_on_esp32:
                esp32_info = await self.get_esp32_tts_info(gesture_label, language)
            
            return {
                "status": "success",
                "laptop_playback": laptop_result or "skipped",
                "esp32_info": esp32_info,
                "language": language,
                "text": text
            }
            
        except Exception as e:
            error_msg = f"Error in speak_gesture: {str(e)}"
            logging.error(error_msg)
            return {
                "status": "error",
                "message": error_msg,
                "gesture": gesture_label,
                "language": language
            }

    async def play_on_laptop(self, audio_path: str):
        """Play audio file on laptop using pygame"""
        if not self.pygame_available:
            return {"status": "error", "message": "pygame not available"}
            
        if not os.path.exists(audio_path):
            return {"status": "error", "message": "Audio file not found"}
            
        try:
            def play_audio():
                try:
                    pygame.mixer.music.load(audio_path)
                    pygame.mixer.music.play()
                    # Wait for playback to finish
                    while pygame.mixer.music.get_busy():
                        pygame.time.wait(100)
                except Exception as e:
                    logging.error(f"Error playing audio on laptop: {e}")
            
            # Start playback in background thread
            audio_thread = threading.Thread(target=play_audio)
            audio_thread.daemon = True
            audio_thread.start()
            
            return {"status": "playing", "location": "laptop"}
        except Exception as e:
            logging.error(f"Failed to play audio on laptop: {e}")
            return {"status": "error", "message": str(e)}

    async def get_esp32_tts_info(self, gesture_label: str, language: str = None):
        """
        Get ESP32 TTS file information for a gesture.
        This helps the ESP32 know which audio file to play from SD card.
        """
        if not self.should_speak_gesture(gesture_label):
            return {"status": "skipped", "reason": "Gesture is idle/basic - no TTS needed"}
            
        lang = language or self.current_language
        esp32_path = self.get_esp32_tts_path(gesture_label, lang)
        gesture_text = self.get_gesture_text(gesture_label, lang)
        
        if not esp32_path:
            return {"status": "error", "message": "Language not supported"}
            
        return {
            "status": "success",
            "gesture_label": gesture_label,
            "language": lang,
            "text": gesture_text,
            "esp32_file_path": esp32_path,
            "filename": esp32_path.split('/')[-1]
        }

    async def _speak_edge(self, text, voice: str = None):
        voice = voice or settings.TTS_VOICE
        cache_path = self.get_cache_path(text, voice)
        if settings.TTS_CACHE_ENABLED and os.path.exists(cache_path):
            return {"status": "success", "provider": "edge", "audio_path": cache_path}
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(cache_path)
        return {"status": "success", "provider": "edge", "audio_path": cache_path}

    async def _speak_gtts(self, text: str):
        cache_path = self.get_cache_path(text, "vi")
        if settings.TTS_CACHE_ENABLED and os.path.exists(cache_path):
            return {"status": "success", "provider": "gtts", "audio_path": cache_path}
        tts = gTTS(text=text, lang="vi")
        tts.save(cache_path)
        return {"status": "success", "provider": "gtts", "audio_path": cache_path}

    async def _speak_pyttsx3(self, text: str):
        if not self.pyttsx3_engine:
            return {"status": "error", "message": "pyttsx3 not available"}
        loop = asyncio.get_event_loop()
        success = await loop.run_in_executor(self.executor, self._pyttsx3_speak, text)
        return {"status": "success" if success else "error", "provider": "pyttsx3"}

    def _pyttsx3_speak(self, text):
        try:
            self.pyttsx3_engine.say(text)
            self.pyttsx3_engine.runAndWait()
            return True
        except:
            return False

    def get_config(self):
        return {
            "config": {
                "provider": settings.TTS_PROVIDER,
                "voice": settings.TTS_VOICE,
                "rate": settings.TTS_RATE,
                "volume": settings.TTS_VOLUME,
                "cache_enabled": settings.TTS_CACHE_ENABLED,
                "cache_dir": settings.TTS_CACHE_DIR
            },
            "available_providers": {
                "pyttsx3": HAS_PYTTSX3,
                "gtts": HAS_GTTS,
                "edge_tts": HAS_EDGE_TTS
            },
            "gesture_mapping": LANGUAGE_MAPPINGS
        }

    def update_config(self, config: dict):
        # This method can be expanded to update settings dynamically if needed
        pass

    def cleanup(self):
        self.executor.shutdown(wait=False)

tts_service = TTSService()