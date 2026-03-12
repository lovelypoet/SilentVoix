import os
import json
import numpy as np
from collections import deque
from core.settings import settings
from AI.runtime_adapter import load_runtime, predict as predict_runtime
from services.model_library_service import model_library_service

# Heavy ML imports wrapped in try/except for API-only environments
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
        # 1. Resolve LSTM model (Classifier)
        base_ai_dir = os.path.join(settings.BASE_DIR, "AI", "models")
        lstm_path = os.path.join(base_ai_dir, "best_model2.pth")
        
        # 2. Resolve YOLO model (Detector)
        self.yolo_path = os.path.join(base_ai_dir, "best.pt")
        registry = model_library_service.load_registry()
        yolo_model = next((m for m in registry.get("models", []) if m.get("metadata", {}).get("export_format") == "yolo"), None)
        if yolo_model:
            self.yolo_path = yolo_model["model_path"]
            print(f"Using YOLO detector from registry: {yolo_model['display_name']}")
        else:
            print(f"No YOLO detector found in registry, using fallback: {self.yolo_path}")

        # 3. Load Models
        self.detector = None
        if YOLO is not None and os.path.exists(self.yolo_path):
            try:
                print(f"Loading YOLO model from: {self.yolo_path}")
                self.detector = YOLO(self.yolo_path)
            except Exception as e:
                print(f"Warning: Failed to load YOLO detector: {e}")
        else:
            print("YOLO detector not available (missing library or model file)")
        
        # LSTM classifier is optional
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
                if self.lstm_runtime:
                    self.classifier = self.lstm_runtime.get("model")
                    self.torch = self.lstm_runtime.get("torch")
                    if self.classifier:
                        self.classifier.to(self.device)
            else:
                print(f"Warning: LSTM model not found at {lstm_path}.")
        except Exception as e:
            print(f"Warning: Failed to load LSTM classifier from {lstm_path}: {e}")
        
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
        self.min_sequence_frames = max(1, min(int(getattr(settings, "INTEGRATED_MIN_FRAMES", 5)), self.sequence_length))

        # 5. MediaPipe Hands (for YOLO -> crop -> MediaPipe -> LSTM pipeline)
        self.mp_hands = None
        self.sequence_pipeline = None
        if YoloMediapipeSequence is not None and self.detector is not None:
            try:
                import mediapipe as mp
                self.mp_hands = mp.solutions.hands.Hands(
                    static_image_mode=False,
                    max_num_hands=1,
                    min_detection_confidence=0.5,
                    min_tracking_confidence=0.5
                )
                self.sequence_pipeline = YoloMediapipeSequence(
                    self.detector,
                    self.mp_hands,
                    sequence_length=self.sequence_length,
                    feature_dim=self.feature_dim
                )
                self.frame_buffer = self.sequence_pipeline.buffer
            except Exception as e:
                print(f"Warning: MediaPipe Hands init failed: {e}")
        else:
            print("Integrated pipeline not available (missing libraries or detector)")


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
        found_hand = False
        current_landmarks = None

        # Preferred pipeline: YOLO bbox -> crop -> MediaPipe -> preprocess
        if self.sequence_pipeline is not None:
            result = self.sequence_pipeline.process_frame(frame)
            found_hand = bool(result.get("hand_detected"))
            current_landmarks = result.get("landmarks")
            current_bbox = result.get("bbox")
        else:
            # Fallback: YOLO keypoints path (pose-only). Kept for compatibility.
            current_bbox = None
            results = self.detector(frame, verbose=False, conf=0.5)[0]
            if results.keypoints is not None and len(results.keypoints.data) > 0:
                raw_kp = results.keypoints.data[0].cpu().numpy() # (21, 3)
                if raw_kp.shape == (21, 3):
                    current_landmarks = raw_kp.tolist()
                    processed_kp = self.preprocess_landmarks(raw_kp)
                    self.frame_buffer.append(processed_kp)
                    found_hand = True
                    # In fallback mode, use keypoints to estimate a rough bbox
                    x1, y1 = np.min(raw_kp[:, :2], axis=0)
                    x2, y2 = np.max(raw_kp[:, :2], axis=0)
                    current_bbox = [int(x1), int(y1), int(x2), int(y2)]

            if not found_hand:
                self.frame_buffer.append(np.zeros(self.feature_dim))

        # Step 2: Classify if buffer is full and classifier is available
        if len(self.frame_buffer) >= self.min_sequence_frames and self.lstm_runtime is not None:
            # Prepare data
            sequence_list = list(self.frame_buffer)
            if len(sequence_list) < self.sequence_length:
                pad_count = self.sequence_length - len(sequence_list)
                pad = [np.zeros(self.feature_dim, dtype=np.float32) for _ in range(pad_count)]
                sequence_list = sequence_list + pad
            sequence_np = np.array(sequence_list, dtype=np.float32)
            
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
                    "landmarks": current_landmarks,
                    "bbox": current_bbox
                }
            except Exception as e:
                print(f"Prediction error: {e}")
                self.reset_buffer()
                return {
                    "gesture": "Error",
                    "confidence": 0.0,
                    "hand_detected": found_hand,
                    "landmarks": current_landmarks,
                    "bbox": current_bbox
                }
        
        return {
            "gesture": "Waiting...",
            "confidence": 0.0,
            "hand_detected": found_hand,
            "landmarks": current_landmarks,
            "bbox": current_bbox
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

    def set_min_sequence_frames(self, min_frames: int):
        """Adjust minimum frames required before running LSTM, clamped to sequence length."""
        try:
            value = int(min_frames)
        except (TypeError, ValueError):
            value = self.min_sequence_frames
        self.min_sequence_frames = max(1, min(value, self.sequence_length))

    def get_integrated_config(self):
        return {
            "min_frames": self.min_sequence_frames,
            "sequence_length": self.sequence_length,
            "feature_dim": self.feature_dim
        }

    def predict_features(self, feature_vec):
        """Predict using precomputed feature vector (e.g., client-side MediaPipe)."""
        try:
            vec = np.array(feature_vec, dtype=np.float32).flatten()
        except Exception:
            vec = np.zeros(self.feature_dim, dtype=np.float32)

        if vec.size > self.feature_dim:
            vec = vec[:self.feature_dim]
        elif vec.size < self.feature_dim:
            vec = np.pad(vec, (0, self.feature_dim - vec.size))

        self.frame_buffer.append(vec)
        found_hand = bool(np.any(vec))

        if len(self.frame_buffer) >= self.min_sequence_frames and self.lstm_runtime is not None:
            sequence_list = list(self.frame_buffer)
            if len(sequence_list) < self.sequence_length:
                pad_count = self.sequence_length - len(sequence_list)
                pad = [np.zeros(self.feature_dim, dtype=np.float32) for _ in range(pad_count)]
                sequence_list = sequence_list + pad
            sequence_np = np.array(sequence_list, dtype=np.float32)
            self.lstm_runtime["metadata"] = {
                "input_spec": {
                    "sequence_length": self.sequence_length,
                    "feature_dim": self.feature_dim
                }
            }

            try:
                logits = predict_runtime(self.lstm_runtime, sequence_np)
                exp_logits = np.exp(logits - np.max(logits))
                probs = exp_logits / exp_logits.sum()
                class_idx = np.argmax(probs)
                return {
                    "gesture": self.labels[class_idx] if class_idx < len(self.labels) else "Unknown",
                    "confidence": float(probs[class_idx]),
                    "hand_detected": found_hand
                }
            except Exception as e:
                print(f"Prediction error: {e}")
                self.reset_buffer()
                return {
                    "gesture": "Error",
                    "confidence": 0.0,
                    "hand_detected": found_hand
                }

        return {
            "gesture": "Waiting...",
            "confidence": 0.0,
            "hand_detected": found_hand
        }

# Singleton instance
_gesture_service = None

def get_gesture_service():
    global _gesture_service
    if _gesture_service is None:
        _gesture_service = GestureService()
    return _gesture_service
