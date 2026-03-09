import os
import json
import numpy as np
import cv2
from collections import deque
from ultralytics import YOLO
from core.settings import settings
from AI.runtime_adapter import load_runtime, predict as predict_runtime
from services.model_library_service import model_library_service

class GestureService:
    def __init__(self):
        # 1. Resolve LSTM model (Classifier)
        # We still use the default path for now, but we'll try to find it in the registry if possible
        base_ai_dir = os.path.join(settings.BASE_DIR, "AI", "models")
        lstm_path = os.path.join(base_ai_dir, "best_model 2.pth")
        
        # 2. Resolve YOLO model (Detector)
        # Try to find a YOLO model in the registry, fallback to best.pt
        self.yolo_path = os.path.join(base_ai_dir, "best.pt")
        registry = model_library_service.load_registry()
        yolo_model = next((m for m in registry.get("models", []) if m.get("metadata", {}).get("export_format") == "yolo"), None)
        if yolo_model:
            self.yolo_path = yolo_model["model_path"]
            print(f"Using YOLO detector from registry: {yolo_model['display_name']}")
        else:
            print(f"No YOLO detector found in registry, using fallback: {self.yolo_path}")

        # 3. Load Models
        print(f"Loading YOLO model from: {self.yolo_path}")
        self.detector = YOLO(self.yolo_path)
        
        # LSTM classifier is optional; if it fails to load we still allow YOLO-only flows.
        self.lstm_runtime = None
        self.classifier = None
        self.torch = None
        self.device = "cpu"

        try:
            if os.path.exists(lstm_path):
                print(f"Loading LSTM model from: {lstm_path}")
                self.lstm_runtime = load_runtime(
                    model_path=lstm_path,
                    export_format="pytorch",
                    is_state_dict=True,
                    has_model_class=True
                )
                self.classifier = self.lstm_runtime["model"]
                self.torch = self.lstm_runtime["torch"]
                self.classifier.to(self.device)
            else:
                print(f"Warning: LSTM model not found at {lstm_path}. Integrated predictor will run without classification.")
        except Exception as e:
            print(f"Warning: Failed to load LSTM classifier from {lstm_path}: {e}")
            self.lstm_runtime = None
            self.classifier = None
            self.torch = None
        
        # 4. Config & Metadata
        self.metadata = {}
        metadata_path = os.path.join(base_ai_dir, "metadata6.json")
        if os.path.exists(metadata_path):
            with open(metadata_path, 'r') as f:
                self.metadata = json.load(f)
        
        self.sequence_length = self.metadata.get("input_spec", {}).get("sequence_length", 16)
        self.feature_dim = self.metadata.get("input_spec", {}).get("feature_dim", 63)
        self.frame_buffer = deque(maxlen=self.sequence_length)
        self.labels = self.metadata.get("labels", ["Goodbye", "Hello", "No", "Thank you", "Yes"])

    def preprocess_landmarks(self, landmarks):
        """
        landmarks: (21, 3) from YOLO (x, y, conf)
        Returns: (63,) flattened normalized keypoints
        """
        # 1. Take only x, y (ignore confidence for this specific model)
        kp = landmarks[:, :2] # (21, 2)
        
        # 2. Center around wrist (index 0)
        wrist = kp[0]
        kp_centered = kp - wrist
        
        # 3. Flatten
        # Note: If the model was trained on 63 dims, it likely expected (x,y,z) or (x,y,0)
        # Assuming (x,y) and adding a dummy 0 for the 3rd dimension to reach 63
        flat = []
        for point in kp_centered:
            flat.extend([point[0], point[1], 0.0])
            
        return np.array(flat, dtype=np.float32)

    def predict_frame(self, frame):
        """
        Processes a single frame and returns the prediction result and landmarks.
        """
        # Step 1: Detect Hand Keypoints
        results = self.detector(frame, verbose=False, conf=0.5)[0]
        
        found_hand = False
        current_landmarks = None
        if results.keypoints is not None and len(results.keypoints.data) > 0:
            # Get first hand detected
            raw_kp = results.keypoints.data[0].cpu().numpy() # (21, 3)
            if raw_kp.shape == (21, 3):
                current_landmarks = raw_kp.tolist() # Convert to list for JSON serialization
                processed_kp = self.preprocess_landmarks(raw_kp)
                self.frame_buffer.append(processed_kp)
                found_hand = True
        
        if not found_hand:
            # If no hand, append zeros to keep temporal consistency
            self.frame_buffer.append(np.zeros(self.feature_dim))

        # Step 2: Classify if buffer is full and classifier is available
        if len(self.frame_buffer) == self.sequence_length and self.lstm_runtime is not None:
            # Prepare data
            sequence_np = np.array(list(self.frame_buffer), dtype=np.float32)
            
            # Use runtime_adapter for prediction
            # We need to inject sequence_length and feature_dim into runtime metadata for predict()
            self.lstm_runtime["metadata"] = {
                "input_spec": {
                    "sequence_length": self.sequence_length,
                    "feature_dim": self.feature_dim
                }
            }
            
            try:
                logits = predict_runtime(self.lstm_runtime, sequence_np)
                
                # Apply softmax to get probabilities
                exp_logits = np.exp(logits - np.max(logits))
                probs = exp_logits / exp_logits.sum()
                
                class_idx = np.argmax(probs)
                
                return {
                    "gesture": self.labels[class_idx] if class_idx < len(self.labels) else "Unknown",
                    "confidence": float(probs[class_idx]),
                    "hand_detected": found_hand,
                    "landmarks": current_landmarks
                }
            except Exception as e:
                print(f"Prediction error: {e}")
                return {
                    "gesture": "Error",
                    "confidence": 0.0,
                    "hand_detected": found_hand,
                    "landmarks": current_landmarks
                }
        
        return {
            "gesture": "Waiting...",
            "confidence": 0.0,
            "hand_detected": found_hand,
            "landmarks": current_landmarks
        }

    def reload_detector_by_id(self, model_id: str):
        """Reloads the YOLO detector using a model ID from the registry."""
        registry = model_library_service.load_registry()
        model_entry = next((m for m in registry.get("models", []) if m.get("id") == model_id), None)
        if not model_entry:
            raise ValueError(f"Model {model_id} not found in registry")
        
        if model_entry.get("metadata", {}).get("export_format") != "yolo":
            raise ValueError(f"Model {model_id} is not a YOLO detector")
            
        self.reload_detector(model_entry["model_path"])

    def reload_detector(self, new_yolo_path: str):
        """Reloads the YOLO detector from a new path."""
        if not os.path.exists(new_yolo_path):
            raise FileNotFoundError(f"YOLO model not found: {new_yolo_path}")
        
        print(f"Reloading YOLO detector from: {new_yolo_path}")
        self.detector = YOLO(new_yolo_path)
        self.yolo_path = new_yolo_path

    def reset_buffer(self):
        """Resets the temporal buffer."""
        self.frame_buffer.clear()

# Singleton instance
_gesture_service = None

def get_gesture_service():
    global _gesture_service
    if _gesture_service is None:
        _gesture_service = GestureService()
    return _gesture_service
