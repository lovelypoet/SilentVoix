import os
import cv2
import json
import argparse
import numpy as np
from tqdm import tqdm
import sys

# Add backend to path to import services and utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.gesture_service import get_gesture_service
from utils.metrics_utils import MetricsEvaluator

def process_video(input_path, output_path=None, ground_truth_path=None):
    """
    Process a video through the YOLO+MediaPipe+LSTM pipeline.
    Optionally saves a processed video with overlays and calculates metrics.
    """
    gesture_service = get_gesture_service()
    gesture_service.reset_buffer()
    
    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        print(f"Error: Could not open video {input_path}")
        return

    # Video properties
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    
    # Output video setup
    writer = None
    if output_path:
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(output_path, fourcc, fps, (width, height))

    # Results collection
    predictions = []
    
    print(f"Processing video: {input_path} ({total_frames} frames)")
    
    for frame_idx in tqdm(range(total_frames)):
        ret, frame = cap.read()
        if not ret:
            break
            
        # Run pipeline
        result = gesture_service.predict_frame(frame)
        predictions.append({
            "frame": frame_idx,
            "gesture": result['gesture'],
            "confidence": result['confidence'],
            "hand_detected": result['hand_detected']
        })
        
        # Draw overlays if writing video
        if writer:
            processed_frame = frame.copy()
            
            # Draw bbox
            if result.get('bbox'):
                x1, y1, x2, y2 = result['bbox']
                cv2.rectangle(processed_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                
            # Draw landmarks
            if result.get('landmarks'):
                for pt in result['landmarks']:
                    x, y = int(pt[0] * width), int(pt[1] * height)
                    cv2.circle(processed_frame, (x, y), 3, (255, 0, 0), -1)
            
            # Draw label
            label = f"{result['gesture']} ({result['confidence']:.2f})"
            cv2.putText(processed_frame, label, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            
            writer.write(processed_frame)
            
    cap.release()
    if writer:
        writer.release()
        print(f"Processed video saved to: {output_path}")

    # Metrics Calculation
    if ground_truth_path:
        with open(ground_truth_path, 'r') as f:
            gt_data = json.load(f)
            
        y_true = []
        y_pred = []
        
        # If ground truth is frame-by-frame
        if 'frames' in gt_data:
            # Map by frame index
            gt_frames = {f['frame']: f['label'] for f in gt_data['frames']}
            for p in predictions:
                f_idx = p['frame']
                if f_idx in gt_frames:
                    y_true.append(gt_frames[f_idx])
                    y_pred.append(p['gesture'])
        
        # If ground truth is segment-based
        elif 'segments' in gt_data:
            gt_frame_labels = MetricsEvaluator.segments_to_frames(gt_data['segments'], total_frames, fps)
            for p in predictions:
                y_true.append(gt_frame_labels[p['frame']])
                y_pred.append(p['gesture'])
                
        if y_true:
            labels = gesture_service.labels + ["rest", "Waiting...", "Error"]
            # Remove duplicates and keep order
            unique_labels = []
            for l in labels:
                if l not in unique_labels:
                    unique_labels.append(l)
                    
            metrics = MetricsEvaluator.calculate_frame_metrics(y_true, y_pred, unique_labels)
            
            # Save metrics
            metrics_out = os.path.splitext(input_path)[0] + "_metrics.json"
            with open(metrics_out, 'w') as f:
                json.dump(metrics, f, indent=2)
            print(f"Metrics saved to: {metrics_out}")
            
            print("\nSummary Metrics:")
            print(f"Accuracy: {metrics['accuracy']:.4f}")
            print(f"F1-Score: {metrics['f1']:.4f}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process video through SilentVoix pipeline")
    parser.add_argument("--input", required=True, help="Input video path")
    parser.add_argument("--output", help="Output video path (optional)")
    parser.add_argument("--gt", help="Ground truth JSON path (optional)")
    
    args = parser.parse_args()
    
    process_video(args.input, args.output, args.gt)
