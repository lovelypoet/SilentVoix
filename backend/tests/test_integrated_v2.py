import torch
import numpy as np
import cv2
from services.gesture_service import GestureService
from AI.models.model_def6 import HandLSTMClassifier
import os

def test_integrated_service():
    print("--- Integrated Gesture Service Test ---")
    
    # Use relative paths for local test
    yolo_model = "AI/models/best.pt"
    lstm_model = "AI/models/best_model 2.pth"
    
    # Check if files exist
    if not os.path.exists(yolo_model):
        print(f"Error: YOLO model not found at {yolo_model}")
        return
    if not os.path.exists(lstm_model):
        print(f"Error: LSTM model not found at {lstm_model}")
        return

    try:
        # Initialize service
        service = GestureService(yolo_path=yolo_model, lstm_path=lstm_model)
        
        # 1. Test with a blank frame (should append zeros)
        print("\nTesting with blank frame (no hand)...")
        blank_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        gesture, score, hand_found = service.predict_frame(blank_frame)
        print(f"Result: Gesture={gesture}, Score={score:.4f}, HandFound={hand_found}")
        print(f"Buffer size: {len(service.frame_buffer)}")
        
        # 2. Test filling the buffer
        print("\nFilling buffer to 16 frames...")
        for i in range(15):
            service.predict_frame(blank_frame)
            
        print(f"Final buffer size: {len(service.frame_buffer)}")
        gesture, score, hand_found = service.predict_frame(blank_frame)
        print(f"Full Loop Result: Gesture={gesture}, Score={score:.4f}, HandFound={hand_found}")
        
        if gesture != "Waiting...":
            print("✅ SUCCESS: Integrated loop returned a prediction.")
        else:
            print("❌ FAILURE: Integrated loop did not return a prediction after 16 frames.")
            
    except Exception as e:
        print(f"❌ ERROR: {e}")

if __name__ == "__main__":
    test_integrated_service()
