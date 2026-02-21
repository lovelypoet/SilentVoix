import os
import math
import random
import re
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple


def _compute_stats(
    series: List[float],
    timestamps_ms: Optional[List[int]],
    sigma_multiplier: float,
    window_size: int,
    persistence: int = 2,
) -> Dict:
    if not series:
        return {
            "threshold": None,
            "spike_index": -1,
            "spike_active": False,
            "spike_timestamp_ms": None,
        }

    if persistence < 2:
        persistence = 2

    start = max(0, len(series) - window_size)
    window = series[start:]
    baseline = window[:-persistence] if len(window) > persistence else window
    mean = sum(baseline) / len(baseline)
    variance = sum((v - mean) ** 2 for v in baseline) / len(baseline)
    sigma = math.sqrt(variance)
    threshold = mean + sigma_multiplier * sigma

    spike_index = -1
    for i in range(1, len(window)):
        if i - 1 + persistence > len(window):
            break
        if window[i] <= threshold:
            continue
        if all(window[j] > threshold for j in range(i - 1, i - 1 + persistence)):
            spike_index = start + i
            break

    spike_timestamp_ms = None
    if spike_index >= 0 and timestamps_ms and 0 <= spike_index < len(timestamps_ms):
        spike_timestamp_ms = int(timestamps_ms[spike_index])

    return {
        "threshold": threshold,
        "spike_index": spike_index,
        "spike_active": spike_index >= 0,
        "spike_timestamp_ms": spike_timestamp_ms,
    }


def _parse_log_timestamp_ms(line: str) -> Optional[int]:
    match = re.match(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})", line)
    if not match:
        return None
    try:
        dt = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S,%f")
    except ValueError:
        return None
    return int(dt.timestamp() * 1000)


def _extract_accel_magnitude_from_line(line: str) -> Optional[Tuple[int, float]]:
    matches = re.findall(r"\[([^\]]+)\]", line)
    if not matches:
        return None

    timestamp_ms = _parse_log_timestamp_ms(line)
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
    if line_peak is None:
        return None
    if timestamp_ms is None:
        timestamp_ms = int(time.time() * 1000)
    return timestamp_ms, line_peak


def _simulate_sensor_samples(max_points: int = 60) -> List[Dict[str, float]]:
    now = time.time()
    phase = now * 1.7
    base = 0.35 + 0.05 * math.sin(phase / 2.0)
    start_ts = int(now * 1000) - (max_points * 100)
    samples: List[Dict[str, float]] = []
    for i in range(max_points):
        wave = 0.12 * math.sin((i + phase) / 6.0)
        noise = random.uniform(-0.03, 0.03)
        samples.append(
            {
                "timestamp_ms": start_ts + (i * 100),
                "value": max(0.0, base + wave + noise),
            }
        )

    # Inject an occasional spike near the end for sync visualization
    if int(now * 2) % 8 == 0 and samples:
        spike_index = max_points - 3
        samples[spike_index]["value"] = samples[spike_index]["value"] + 0.6
        samples[spike_index + 1]["value"] = samples[spike_index + 1]["value"] + 0.4
    return samples


def _truthy_env(value: Optional[str]) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_sensor_samples(mode: str, limit: int = 200, max_points: int = 60, simulate: bool = False) -> List[Dict[str, float]]:
    if simulate or _truthy_env(os.getenv("SYNC_SENSOR_SIM")):
        return _simulate_sensor_samples(max_points=max_points)

    log_filename = "data_collection.log" if mode == "single" else "dual_hand_data_collection.log"
    base_dir = os.path.join(os.path.dirname(__file__))
    path = os.path.abspath(os.path.join(base_dir, log_filename))
    if not os.path.exists(path):
        return _simulate_sensor_samples(max_points=max_points) if _truthy_env(os.getenv("SYNC_SENSOR_SIM")) else []
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()[-limit:]
    except Exception:
        return []
    samples: List[Dict[str, float]] = []
    for line in lines:
        sample = _extract_accel_magnitude_from_line(line)
        if sample is not None:
            timestamp_ms, mag = sample
            samples.append({"timestamp_ms": int(timestamp_ms), "value": float(mag)})
    return samples[-max_points:]


class SyncStreamBuffer:
    def __init__(self, max_points: int = 60):
        self.max_points = max_points
        self.cv_samples: List[Dict[str, float]] = []

    def add_cv_sample(self, velocity: float, timestamp_ms: Optional[int] = None) -> None:
        if not math.isfinite(velocity):
            return
        if timestamp_ms is None:
            timestamp_ms = int(time.time() * 1000)
        self.cv_samples.append({"timestamp_ms": int(timestamp_ms), "value": float(velocity)})
        if len(self.cv_samples) > self.max_points:
            self.cv_samples = self.cv_samples[-self.max_points:]

    def get_cv_samples(self) -> List[Dict[str, float]]:
        return list(self.cv_samples)

    def compute_sensor_stats(self, samples: List[Dict[str, float]], window_size: int = 20) -> Dict:
        series = [float(item["value"]) for item in samples]
        timestamps = [int(item["timestamp_ms"]) for item in samples]
        return _compute_stats(series, timestamps, sigma_multiplier=6.0, window_size=window_size)

    def compute_cv_stats(self, samples: List[Dict[str, float]], window_size: int = 20) -> Dict:
        series = [float(item["value"]) for item in samples]
        timestamps = [int(item["timestamp_ms"]) for item in samples]
        return _compute_stats(series, timestamps, sigma_multiplier=5.0, window_size=window_size)
