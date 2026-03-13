from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, List, Sequence, Tuple

import numpy as np


SENSOR_ORDER_IMU_FLEX = "imu_flex"  # ax, ay, az, gx, gy, gz, f1..f5
SENSOR_ORDER_FLEX_IMU = "flex_imu"  # f1..f5, ax, ay, az, gx, gy, gz


def _xyz(point: Any) -> Tuple[float, float, float]:
    if isinstance(point, dict):
        return float(point.get("x", 0.0)), float(point.get("y", 0.0)), float(point.get("z", 0.0))
    return float(getattr(point, "x", 0.0)), float(getattr(point, "y", 0.0)), float(getattr(point, "z", 0.0))


def normalize_hand_to_wrist(hand: Any) -> List[float]:
    """Match docs/early_fusion.md: wrist-relative 21x3 -> 63 values."""
    if not isinstance(hand, Sequence) or len(hand) != 21:
        return [0.0] * 63
    wx, wy, wz = _xyz(hand[0])
    values: List[float] = []
    for i in range(21):
        x, y, z = _xyz(hand[i])
        values.extend([x - wx, y - wy, z - wz])
    return values


def normalize_sensor(values: Iterable[Any], dim: int = 11, order: str = SENSOR_ORDER_IMU_FLEX) -> List[float]:
    raw = [float(v or 0.0) for v in list(values)]
    if len(raw) == 12:
        raw = raw[1:]
    if len(raw) > dim:
        raw = raw[:dim]
    if order == SENSOR_ORDER_FLEX_IMU and len(raw) == 11:
        flex = raw[:5]
        accel = raw[5:8]
        gyro = raw[8:11]
        raw = accel + gyro + flex
    out = raw
    if len(out) < dim:
        out.extend([0.0] * (dim - len(out)))
    return out


def pad_or_trim(values: Sequence[float], target_dim: int) -> List[float]:
    if len(values) > target_dim:
        return list(values[:target_dim])
    if len(values) < target_dim:
        return list(values) + [0.0] * (target_dim - len(values))
    return list(values)


def build_fused_frame(
    hand: Any,
    sensor_values: Iterable[Any],
    feature_dim: int = 74,
    sensor_dim: int = 11,
    sensor_order: str = SENSOR_ORDER_IMU_FLEX,
) -> np.ndarray:
    cv_values = normalize_hand_to_wrist(hand)
    sensor = normalize_sensor(sensor_values, dim=sensor_dim, order=sensor_order)
    fused = pad_or_trim(cv_values + sensor, feature_dim)
    return np.asarray(fused, dtype=np.float32)


def summarize_vector(values: Sequence[float]) -> dict:
    if not values:
        return {"len": 0, "zeros": 0, "min": 0.0, "max": 0.0, "mean": 0.0}
    zeros = 0
    total = 0.0
    min_v = float("inf")
    max_v = float("-inf")
    for v in values:
        num = float(v or 0.0)
        if num == 0.0:
            zeros += 1
        total += num
        if num < min_v:
            min_v = num
        if num > max_v:
            max_v = num
    return {
        "len": len(values),
        "zeros": zeros,
        "min": min_v if min_v != float("inf") else 0.0,
        "max": max_v if max_v != float("-inf") else 0.0,
        "mean": total / len(values),
    }


@dataclass
class EarlyFusionBuffer:
    sequence_length: int = 30
    feature_dim: int = 74
    frames: List[np.ndarray] = field(default_factory=list)

    def push(self, frame: Sequence[float] | np.ndarray) -> None:
        vec = np.asarray(frame, dtype=np.float32).reshape(-1)
        if vec.size != self.feature_dim:
            vec = np.asarray(pad_or_trim(vec.tolist(), self.feature_dim), dtype=np.float32)
        self.frames.append(vec)
        if len(self.frames) > self.sequence_length:
            self.frames = self.frames[-self.sequence_length :]

    def ready(self) -> bool:
        return len(self.frames) >= self.sequence_length

    def as_batch(self) -> np.ndarray:
        return np.asarray(self.frames, dtype=np.float32)[None, ...]
