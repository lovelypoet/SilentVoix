# backend/ingestion/streaming/movement_detector.py

import numpy as np

class MovementDetector:
    """
    Detects and collects full movement sequences.
    A movement starts when variance > threshold, and ends when it stabilizes.
    """

    def __init__(self, threshold: float = 0.05, window_size: int = 5, min_length: int = 10):
        self.threshold = threshold
        self.window_size = window_size
        self.min_length = min_length
        self.buffer = []         # short-term window
        self.sequence = []       # active movement sequence
        self.in_motion = False

    def update(self, sensor_values):
        """
        Feed in a new frame of sensor values.
        Returns None if still collecting,
        Returns a full sequence (list of frames) when movement ends.
        """
        self.buffer.append(sensor_values)
        if len(self.buffer) > self.window_size:
            self.buffer.pop(0)

        if len(self.buffer) < self.window_size:
            return None

        arr = np.array(self.buffer)
        variances = np.var(arr, axis=0)
        is_moving = np.any(variances > self.threshold)

        if is_moving and not self.in_motion:
            # movement starts
            self.in_motion = True
            self.sequence = []

        if self.in_motion:
            self.sequence.append(sensor_values)

        if not is_moving and self.in_motion:
            # movement ended
            self.in_motion = False
            if len(self.sequence) >= self.min_length:
                finished = self.sequence
                self.sequence = []
                return finished

        return None
