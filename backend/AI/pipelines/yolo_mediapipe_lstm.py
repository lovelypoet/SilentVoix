import cv2
import numpy as np
from collections import deque


class YoloMediapipeSequence:
    """
    Realtime pipeline:
      YOLO bbox -> crop -> MediaPipe Hands -> preprocess -> temporal buffer
    """

    def __init__(self, yolo_model, mp_hands, sequence_length=16, feature_dim=63):
        self.yolo = yolo_model
        self.hands = mp_hands
        self.sequence_length = int(sequence_length or 16)
        self.feature_dim = int(feature_dim or 63)
        self.buffer = deque(maxlen=self.sequence_length)

    def reset(self):
        self.buffer.clear()

    def _clip_box(self, x1, y1, x2, y2, width, height):
        x1 = max(0, min(int(x1), width - 1))
        y1 = max(0, min(int(y1), height - 1))
        x2 = max(0, min(int(x2), width))
        y2 = max(0, min(int(y2), height))
        if x2 <= x1 or y2 <= y1:
            return None
        return x1, y1, x2, y2

    def _preprocess_landmarks(self, landmarks):
        kp = np.array([[lm.x, lm.y] for lm in landmarks], dtype=np.float32)
        if kp.shape[0] == 0:
            return np.zeros(self.feature_dim, dtype=np.float32)
        wrist = kp[0]
        kp_centered = kp - wrist

        flat = []
        for p in kp_centered:
            flat.extend([float(p[0]), float(p[1]), 0.0])
        vec = np.array(flat, dtype=np.float32)

        if vec.size > self.feature_dim:
            return vec[:self.feature_dim]
        if vec.size < self.feature_dim:
            return np.pad(vec, (0, self.feature_dim - vec.size))
        return vec

    def process_frame(self, frame):
        """
        Returns:
          - hand_detected: bool
          - landmarks: list of 21 points in full-frame normalized coords (for UI)
          - bbox: list of [x1, y1, x2, y2] in pixel coords
        """
        height, width = frame.shape[:2]
        feature = np.zeros(self.feature_dim, dtype=np.float32)
        hand_detected = False
        ui_landmarks = None
        current_bbox = None

        results = self.yolo(frame, verbose=False, conf=0.5)[0]
        if results.boxes is not None and len(results.boxes) > 0:
            box = results.boxes.xyxy[0].cpu().numpy()
            clipped = self._clip_box(*box, width=width, height=height)
            if clipped is not None:
                x1, y1, x2, y2 = clipped
                current_bbox = [x1, y1, x2, y2]
                crop = frame[y1:y2, x1:x2]
                if crop.size != 0:
                    rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
                    mp_result = self.hands.process(rgb)
                    if mp_result.multi_hand_landmarks:
                        landmarks = mp_result.multi_hand_landmarks[0].landmark
                        feature = self._preprocess_landmarks(landmarks)
                        hand_detected = True

                        crop_h, crop_w = crop.shape[:2]
                        ui_landmarks = []
                        for lm in landmarks:
                            x = (x1 + lm.x * crop_w) / float(width)
                            y = (y1 + lm.y * crop_h) / float(height)
                            ui_landmarks.append([float(x), float(y), 0.0])

        if not hand_detected:
            feature = np.zeros(self.feature_dim, dtype=np.float32)

        self.buffer.append(feature)
        return {
            "hand_detected": hand_detected,
            "landmarks": ui_landmarks,
            "bbox": current_bbox
        }

