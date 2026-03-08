import cv2
import torch
import numpy as np
from collections import deque
from ultralytics import YOLO
from pathlib import Path
import logging
from AI.models.model_def6 import HandLSTMClassifier

logger = logging.getLogger("signglove.gesture_service")

class GestureService:
    def __init__(self, yolo_path: str = None, lstm_path: str = None, device: str = 'cpu'):
        self.device = device
        
        # Paths
        base_dir = Path(__file__).parent.parent.resolve()
        yolo_path = yolo_path or str(base_dir / "AI" / "models" / "best.pt")
        lstm_path = lstm_path or str(base_dir / "AI" / "models" / "best_model 2.pth")
        
        logger.info(f"Loading YOLO model from: {yolo_path}")
        self.detector = YOLO(yolo_path)
        
        logger.info(f"Loading LSTM model from: {lstm_path}")
        # Parameters from metadata6.json: feature_dim=63, hidden=256, layers=2, classes=5
        self.classifier = HandLSTMClassifier(feature_dim=63, hidden=256, num_layers=2, num_classes=5)
        self.classifier.load_state_dict(torch.load(lstm_path, map_location=device, weights_only=True))
        self.classifier.to(device)
        self.classifier.eval()
        
        # Setup Temporal Buffer (16 frames)
        self.sequence_length = 16
        self.feature_dim = 63
        self.frame_buffer = deque(maxlen=self.sequence_length)
        self.labels = ['Goodbye', 'Hello', 'No', 'Thank you', 'Yes']
        
        logger.info("GestureService initialized successfully.")

    def preprocess_landmarks(self, landmarks):
        """
        Wrist-centering + Scale normalization as per integration guide.
        landmarks shape: (21, 3) -> [x, y, conf]
        """
        # landmarks shape: (21, 3) -> [x, y, conf]
        coords = landmarks[:, :2] # We only use X, Y for the math
        
        # Wrist is index 0
        wrist = coords[0]
        coords = coords - wrist
        
        # Scale by distance from Wrist(0) to Middle MCP(9)
        # Add epsilon to avoid division by zero
        scale = np.linalg.norm(coords[9] - coords[0]) + 1e-6
        coords = coords / scale
        
        # Flatten back to 63
        return coords.flatten()

    def predict_frame(self, frame):
        """
        Processes a single frame and returns the prediction if the buffer is full.
        """
        # Step 1: Detect Hand Keypoints
        results = self.detector(frame, verbose=False, conf=0.5)[0]
        
        found_hand = False
        if results.keypoints is not None and len(results.keypoints.data) > 0:
            # Get first hand detected
            raw_kp = results.keypoints.data[0].cpu().numpy() # (21, 3)
            if raw_kp.shape == (21, 3):
                processed_kp = self.preprocess_landmarks(raw_kp)
                self.frame_buffer.append(processed_kp)
                found_hand = True
        
        if not found_hand:
            # If no hand, append zeros to keep temporal consistency
            self.frame_buffer.append(np.zeros(self.feature_dim))

        # Step 2: Classify if buffer is full
        if len(self.frame_buffer) == self.sequence_length:
            # Convert buffer to tensor (1, 16, 63)
            # Optimization: Convert to numpy array first to avoid slow list-to-tensor conversion
            sequence_np = np.array(list(self.frame_buffer), dtype=np.float32)
            input_tensor = torch.from_numpy(sequence_np).unsqueeze(0).to(self.device)
            
            with torch.no_grad():
                prediction = self.classifier(input_tensor)
                confidence = torch.softmax(prediction, dim=1)
                class_idx = torch.argmax(confidence).item()
                
                return self.labels[class_idx], confidence[0][class_idx].item(), found_hand
        
        return "Waiting...", 0.0, found_hand

    def reset_buffer(self):
        """Resets the temporal buffer."""
        self.frame_buffer.clear()

# Singleton instance
gesture_service = None

def get_gesture_service():
    global gesture_service
    if gesture_service is None:
        gesture_service = GestureService()
    return gesture_service
