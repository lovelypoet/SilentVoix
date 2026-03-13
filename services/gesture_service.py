from __future__ import annotations
import os
import json
import numpy as np
import httpx
import logging
from collections import deque
from typing import Dict, Any, List, Optional
from api.core.settings import settings
from AI.runtime_adapter import normalize_export_format
from services.model_library_service import model_library_service

logger = logging.getLogger("signglove.gesture_service")

# Optional ML imports for local fallback (only if installed)
try:
    import cv2
except ImportError:
    cv2 = None

try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None

try:
    from AI.pipelines.yolo_mediapipe_lstm import YoloMediapipeSequence
except ImportError:
    YoloMediapipeSequence = None

class GestureService:
    def __init__(self):
        # 1. Resolve Paths (for potential remote or local use)
        base_ai_dir = os.path.join(settings.BASE_DIR, "AI", "models")
        self.yolo_path = os.path.join(base_ai_dir, "best.pt")
        
        # 2. Setup Deque
        # We need these even in proxy mode to keep track of state if we do temporal buffering in the API
        self.sequence_length = 16
        self.feature_dim = 63
        self.frame_buffer = deque(maxlen=self.sequence_length)
        self.labels = ["Goodbye", "Hello", "No", "Thank you", "Yes"]
        self.min_sequence_frames = 5
        self.detector = None
        self.sequence_pipeline = None

        # 3. Load Metadata (optional)
        metadata_path = os.path.join(base_ai_dir, "metadata6.json")
        if os.path.exists(metadata_path):
            try:
                with open(metadata_path, 'r') as f:
                    meta = json.load(f)
                    self.sequence_length = meta.get("input_spec", {}).get("sequence_length", 16)
                    self.feature_dim = meta.get("input_spec", {}).get("feature_dim", 63)
                    self.labels = meta.get("labels", self.labels)
                    self.frame_buffer = deque(maxlen=self.sequence_length)
            except Exception as e:
                logger.warning(f"Failed to load gesture metadata: {e}")

        # 4. Local Fallback Loading (only if NOT using runtime services and libs are present)
        if not settings.USE_RUNTIME_SERVICES:
            self._init_local_models()

    def _init_local_models(self):
        """Initialize models locally if libraries and files are available."""
        if YOLO is None or cv2 is None:
            logger.info("Local ML libraries (ultralytics/cv2) not found. Local fallback disabled.")
            return

        registry = model_library_service.load_registry()
        yolo_model = next((m for m in registry.get("models", []) if m.get("metadata", {}).get("export_format") == "yolo"), None)
        if yolo_model:
            self.yolo_path = yolo_model["model_path"]
        
        if os.path.exists(self.yolo_path):
            try:
                self.detector = YOLO(self.yolo_path)
                logger.info(f"Loaded local YOLO detector: {self.yolo_path}")
            except Exception as e:
                logger.error(f"Failed to load local YOLO: {e}")

        if YoloMediapipeSequence is not None and self.detector is not None:
            try:
                import mediapipe as mp
                mp_hands = mp.solutions.hands.Hands(
                    static_image_mode=False,
                    max_num_hands=1,
                    min_detection_confidence=0.5,
                    min_tracking_confidence=0.5
                )
                self.sequence_pipeline = YoloMediapipeSequence(
                    self.detector,
                    mp_hands,
                    sequence_length=self.sequence_length,
                    feature_dim=self.feature_dim
                )
                self.frame_buffer = self.sequence_pipeline.buffer
                logger.info("Loaded local integrated pipeline (YOLO+MediaPipe)")
            except Exception as e:
                logger.error(f"Failed to init local pipeline: {e}")

    def predict_frame(self, frame: np.ndarray) -> Dict[str, Any]:
        """
        Processes a single frame. Delegates to remote service or local fallback.
        """
        if settings.USE_RUNTIME_SERVICES:
            return self._predict_remote_frame(frame)
        
        if self.sequence_pipeline:
            return self._predict_local_frame(frame)
        
        return {
            "gesture": "Service Unavailable",
            "confidence": 0.0,
            "hand_detected": False,
            "landmarks": None,
            "message": "Local ML models not loaded and remote services disabled."
        }

    def _predict_remote_frame(self, frame: np.ndarray) -> Dict[str, Any]:
        """
        Forward the frame to a remote ML service.
        Note: This requires an 'integrated' endpoint on the remote side.
        If not available, this is a placeholder for future extension.
        """
        # For now, if no integrated remote exists, we might just return 'Waiting...'
        # or implement a specific call to a worker.
        return {
            "gesture": "Remote Inference Pending",
            "confidence": 0.0,
            "hand_detected": False,
            "landmarks": None,
            "message": "Remote integrated inference not yet implemented in GestureService proxy."
        }

    def _predict_local_frame(self, frame: np.ndarray) -> Dict[str, Any]:
        """Original local prediction logic using local models."""
        if not self.sequence_pipeline:
            return {"gesture": "Error", "confidence": 0.0, "hand_detected": False}
            
        result = self.sequence_pipeline.process_frame(frame)
        found_hand = bool(result.get("hand_detected"))
        current_landmarks = result.get("landmarks")
        current_bbox = result.get("bbox")
        
        # Classification logic (LSTM) would go here if we had a local LSTM runtime.
        # For now, we return the detector results.
        return {
            "gesture": "Waiting...", # Classification needs LSTM
            "confidence": 0.0,
            "hand_detected": found_hand,
            "landmarks": current_landmarks,
            "bbox": current_bbox
        }

    def reset_buffer(self):
        self.frame_buffer.clear()

    def set_min_sequence_frames(self, min_frames: int):
        self.min_sequence_frames = max(1, min(int(min_frames), self.sequence_length))

    def get_integrated_config(self):
        return {
            "min_frames": self.min_sequence_frames,
            "sequence_length": self.sequence_length,
            "feature_dim": self.feature_dim
        }

    def predict_features(self, feature_vec: List[float]) -> Dict[str, Any]:
        """
        Predict using features. This can be done locally even in API 
        if we call the remote classifier for the final step.
        """
        vec = np.array(feature_vec, dtype=np.float32).flatten()
        if vec.size > self.feature_dim:
            vec = vec[:self.feature_dim]
        elif vec.size < self.feature_dim:
            vec = np.pad(vec, (0, self.feature_dim - vec.size))

        self.frame_buffer.append(vec)
        found_hand = bool(np.any(vec))

        if len(self.frame_buffer) >= self.min_sequence_frames:
            if settings.USE_RUNTIME_SERVICES:
                return self._predict_remote_classifier(list(self.frame_buffer))
            
            # Local fallback for classifier not implemented here for brevity
            # (would call local LSTM runtime)
        
        return {"gesture": "Waiting...", "confidence": 0.0, "hand_detected": found_hand}

    def _predict_remote_classifier(self, sequence: List[np.ndarray]) -> Dict[str, Any]:
        """Call remote ml-pytorch/tensorflow for sequence classification."""
        # Find active classifier in registry
        registry = model_library_service.load_registry()
        active_id = registry.get("active_model_id")
        if not active_id:
            return {"gesture": "No Active Model", "confidence": 0.0}
            
        entry = model_library_service.get_model_entry(registry, active_id)
        input_vector = np.array(sequence).flatten()
        
        try:
            result = model_library_service.remote_predict(entry, input_vector)
            pred = result.get("prediction", {})
            return {
                "gesture": pred.get("label", "Unknown"),
                "confidence": pred.get("confidence", 0.0),
                "hand_detected": True
            }
        except Exception as e:
            logger.error(f"Remote classification failed: {e}")
            return {"gesture": "Error", "confidence": 0.0}

    def reload_detector_by_id(self, model_id: str):
        if settings.USE_RUNTIME_SERVICES:
            # Remote detector switching would happen in the runtime service
            logger.info(f"Remote detector switch requested for {model_id}")
            return
            
        registry = model_library_service.load_registry()
        model_entry = next((m for m in registry.get("models", []) if m.get("id") == model_id), None)
        if model_entry:
            self.yolo_path = model_entry["model_path"]
            if YOLO:
                self.detector = YOLO(self.yolo_path)

# Singleton instance
_gesture_service = None

def get_gesture_service():
    global _gesture_service
    if _gesture_service is None:
        _gesture_service = GestureService()
    return _gesture_service
