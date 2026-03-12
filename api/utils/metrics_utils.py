import numpy as np
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix

class MetricsEvaluator:
    """
    Utility to calculate gesture recognition metrics from predictions and ground truth.
    """
    
    @staticmethod
    def calculate_frame_metrics(y_true, y_pred, labels):
        """
        Calculate metrics for frame-by-frame predictions.
        
        Args:
            y_true: List of true labels (strings)
            y_pred: List of predicted labels (strings)
            labels: List of all possible labels
            
        Returns:
            Dictionary containing accuracy, precision, recall, f1, and confusion_matrix.
        """
        if not y_true or not y_pred:
            return None
            
        accuracy = accuracy_score(y_true, y_pred)
        precision, recall, f1, _ = precision_recall_fscore_support(
            y_true, y_pred, labels=labels, average='macro', zero_division=0
        )
        
        cm = confusion_matrix(y_true, y_pred, labels=labels)
        
        # Per-class metrics
        class_precision, class_recall, class_f1, _ = precision_recall_fscore_support(
            y_true, y_pred, labels=labels, average=None, zero_division=0
        )
        
        per_label_metrics = {}
        for i, label in enumerate(labels):
            per_label_metrics[label] = {
                "precision": float(class_precision[i]),
                "recall": float(class_recall[i]),
                "f1": float(class_f1[i])
            }
            
        return {
            "accuracy": float(accuracy),
            "precision": float(precision),
            "recall": float(recall),
            "f1": float(f1),
            "per_label_metrics": per_label_metrics,
            "confusion_matrix": cm.tolist(),
            "labels": labels
        }

    @staticmethod
    def segments_to_frames(segments, total_frames, fps):
        """
        Convert timed segments into a frame-by-frame label list.
        
        Args:
            segments: List of dicts [{"label": "hello", "start_s": 1.0, "end_s": 2.5}, ...]
            total_frames: Total number of frames in video
            fps: Frames per second
            
        Returns:
            List of labels for each frame. Default to "rest" or "unknown" if not in segment.
        """
        frame_labels = ["rest"] * total_frames
        
        for seg in segments:
            start_frame = int(seg['start_s'] * fps)
            end_frame = int(seg['end_s'] * fps)
            
            # Clip to video length
            start_frame = max(0, min(start_frame, total_frames - 1))
            end_frame = max(0, min(end_frame, total_frames - 1))
            
            for f in range(start_frame, end_frame + 1):
                frame_labels[f] = seg['label']
                
        return frame_labels
