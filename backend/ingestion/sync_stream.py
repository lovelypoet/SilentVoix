import os
import math
import re
from typing import Dict, List, Tuple, Optional


def _compute_stats(series: List[float], sigma_multiplier: float, window_size: int) -> Dict:
    if not series:
        return {"threshold": None, "spike_index": -1, "spike_active": False}
    start = max(0, len(series) - window_size)
    window = series[start:]
    mean = sum(window) / len(window)
    variance = sum((v - mean) ** 2 for v in window) / len(window)
    sigma = math.sqrt(variance)
    threshold = mean + sigma_multiplier * sigma
    spike_index = -1
    spike_active = False
    if len(series) >= 2:
        i = len(series) - 1
        if series[i] > threshold and series[i - 1] > threshold:
            spike_index = i
            spike_active = True
    return {"threshold": threshold, "spike_index": spike_index, "spike_active": spike_active}


def _extract_accel_magnitude_from_line(line: str) -> Optional[float]:
    matches = re.findall(r"\[([^\]]+)\]", line)
    if not matches:
        return None
    line_peak = None
    for m in matches:
        nums = []
        for part in m.split(","):
            part = part.strip()
            try:
                nums.append(float(part))
            except ValueError:
                continue
        if len(nums) >= 8:
            ax, ay, az = nums[5], nums[6], nums[7]
            mag = math.sqrt(ax * ax + ay * ay + az * az)
            line_peak = mag if line_peak is None else max(line_peak, mag)
    return line_peak


def load_sensor_series(mode: str, limit: int = 200, max_points: int = 60) -> List[float]:
    log_filename = "data_collection.log" if mode == "single" else "dual_hand_data_collection.log"
    base_dir = os.path.join(os.path.dirname(__file__))
    path = os.path.abspath(os.path.join(base_dir, log_filename))
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()[-limit:]
    except Exception:
        return []
    series: List[float] = []
    for line in lines:
        mag = _extract_accel_magnitude_from_line(line)
        if mag is not None:
            series.append(mag)
    return series[-max_points:]


class SyncStreamBuffer:
    def __init__(self, max_points: int = 60):
        self.max_points = max_points
        self.cv_series: List[float] = []

    def add_cv_sample(self, velocity: float) -> None:
        if not math.isfinite(velocity):
            return
        self.cv_series.append(float(velocity))
        if len(self.cv_series) > self.max_points:
            self.cv_series = self.cv_series[-self.max_points:]

    def get_cv_series(self) -> List[float]:
        return list(self.cv_series)

    def compute_sensor_stats(self, series: List[float], window_size: int = 20) -> Dict:
        return _compute_stats(series, sigma_multiplier=6.0, window_size=window_size)

    def compute_cv_stats(self, series: List[float], window_size: int = 20) -> Dict:
        return _compute_stats(series, sigma_multiplier=5.0, window_size=window_size)
