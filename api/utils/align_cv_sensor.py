#!/usr/bin/env python3
"""Align CV landmark CSV with sensor CSV(s) using event-based sync.

Usage examples:
  python backend/utils/align_cv_sensor.py --cv path/to/cv.csv --sensor path/to/sensor.csv
  python backend/utils/align_cv_sensor.py --cv path/to/cv.csv --sensor-left left.csv --sensor-right right.csv
"""

import argparse
import csv
import json
import math
import os
from typing import List, Tuple, Optional


def rolling_stats(window: List[float]) -> Tuple[float, float]:
    if not window:
        return 0.0, 0.0
    mean = sum(window) / len(window)
    var = sum((x - mean) ** 2 for x in window) / len(window)
    return mean, math.sqrt(var)


def detect_spike(times: List[float], values: List[float], k: float, window: int, min_consecutive: int) -> Optional[float]:
    if len(values) < window + min_consecutive:
        return None
    consecutive = 0
    for i in range(window, len(values)):
        mean, std = rolling_stats(values[i - window:i])
        threshold = mean + k * std
        if std > 0 and values[i] > threshold:
            consecutive += 1
            if consecutive >= min_consecutive:
                return times[i - min_consecutive + 1]
        else:
            consecutive = 0
    return None


def read_csv(path: str) -> Tuple[List[str], List[dict]]:
    with open(path, newline='') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        return reader.fieldnames or [], rows


def get_float(row: dict, key: str, default: float = 0.0) -> float:
    try:
        return float(row.get(key, default))
    except (TypeError, ValueError):
        return default


def cv_velocity_series(rows: List[dict]) -> Tuple[List[float], List[float]]:
    times = []
    velocities = []
    prev_pos = None
    prev_t = None

    for row in rows:
        t = get_float(row, 'timestamp_ms', None)
        if t is None:
            continue

        l_exist = int(get_float(row, 'L_exist', 0))
        r_exist = int(get_float(row, 'R_exist', 0))

        if l_exist:
            x = get_float(row, 'L_x0')
            y = get_float(row, 'L_y0')
            z = get_float(row, 'L_z0')
        elif r_exist:
            x = get_float(row, 'R_x0')
            y = get_float(row, 'R_y0')
            z = get_float(row, 'R_z0')
        else:
            prev_pos = None
            prev_t = t
            continue

        if prev_pos is not None and prev_t is not None:
            dt = t - prev_t
            if dt > 0:
                dx = x - prev_pos[0]
                dy = y - prev_pos[1]
                dz = z - prev_pos[2]
                speed = math.sqrt(dx * dx + dy * dy + dz * dz) / dt
                times.append(t)
                velocities.append(speed)

        prev_pos = (x, y, z)
        prev_t = t

    return times, velocities


def sensor_mag_series_single(rows: List[dict]) -> Tuple[List[float], List[float]]:
    times = []
    mags = []
    for row in rows:
        t = get_float(row, 'timestamp_ms', None)
        if t is None:
            continue
        ax = get_float(row, 'accel_x')
        ay = get_float(row, 'accel_y')
        az = get_float(row, 'accel_z')
        mag = math.sqrt(ax * ax + ay * ay + az * az)
        times.append(t)
        mags.append(mag)
    return times, mags


def sensor_mag_series_dual(rows: List[dict], prefix: str) -> Tuple[List[float], List[float]]:
    times = []
    mags = []
    ax_key = f'{prefix}_acc_1'
    ay_key = f'{prefix}_acc_2'
    az_key = f'{prefix}_acc_3'
    for row in rows:
        t = get_float(row, 'timestamp_ms', None)
        if t is None:
            continue
        ax = get_float(row, ax_key)
        ay = get_float(row, ay_key)
        az = get_float(row, az_key)
        mag = math.sqrt(ax * ax + ay * ay + az * az)
        times.append(t)
        mags.append(mag)
    return times, mags


def main():
    parser = argparse.ArgumentParser(description='Align CV and sensor streams using sync spikes.')
    parser.add_argument('--cv', required=True, help='Path to CV CSV')
    parser.add_argument('--sensor', help='Path to single-hand sensor CSV')
    parser.add_argument('--sensor-left', help='Path to dual-hand left CSV (or combined CSV)')
    parser.add_argument('--sensor-right', help='Path to dual-hand right CSV (or combined CSV)')
    parser.add_argument('--out', default='sync_metadata.json', help='Output metadata JSON path')
    parser.add_argument('--cv-k', type=float, default=5.0, help='CV spike threshold multiplier (default 5)')
    parser.add_argument('--sensor-k', type=float, default=6.0, help='Sensor spike threshold multiplier (default 6)')
    parser.add_argument('--window', type=int, default=50, help='Rolling window size for stats')
    parser.add_argument('--min-consecutive', type=int, default=2, help='Min consecutive samples to confirm spike')

    args = parser.parse_args()

    cv_header, cv_rows = read_csv(args.cv)
    if 'timestamp_ms' not in cv_header:
        raise SystemExit('CV CSV missing timestamp_ms')

    cv_times, cv_vels = cv_velocity_series(cv_rows)
    cv_spike_t = detect_spike(cv_times, cv_vels, args.cv_k, args.window, args.min_consecutive)

    sensor_mode = None
    left_spike = None
    right_spike = None
    sensor_header = []

    if args.sensor:
        sensor_mode = 'single'
        sensor_header, sensor_rows = read_csv(args.sensor)
        if 'timestamp_ms' not in sensor_header:
            raise SystemExit('Sensor CSV missing timestamp_ms')
        s_times, s_vals = sensor_mag_series_single(sensor_rows)
        left_spike = detect_spike(s_times, s_vals, args.sensor_k, args.window, args.min_consecutive)
    else:
        if not args.sensor_left:
            raise SystemExit('Provide --sensor or --sensor-left/--sensor-right')
        sensor_mode = 'dual'
        sensor_header, sensor_rows = read_csv(args.sensor_left)
        if 'timestamp_ms' not in sensor_header:
            raise SystemExit('Sensor CSV missing timestamp_ms')
        if 'left_acc_1' in sensor_header:
            left_times, left_vals = sensor_mag_series_dual(sensor_rows, 'left')
            right_times, right_vals = sensor_mag_series_dual(sensor_rows, 'right')
            left_spike = detect_spike(left_times, left_vals, args.sensor_k, args.window, args.min_consecutive)
            right_spike = detect_spike(right_times, right_vals, args.sensor_k, args.window, args.min_consecutive)
        else:
            # If left/right are separate files
            if not args.sensor_right:
                raise SystemExit('Dual-hand mode requires combined CSV with left/right columns or --sensor-right')
            left_header, left_rows = read_csv(args.sensor_left)
            right_header, right_rows = read_csv(args.sensor_right)
            left_times, left_vals = sensor_mag_series_single(left_rows)
            right_times, right_vals = sensor_mag_series_single(right_rows)
            left_spike = detect_spike(left_times, left_vals, args.sensor_k, args.window, args.min_consecutive)
            right_spike = detect_spike(right_times, right_vals, args.sensor_k, args.window, args.min_consecutive)

    result = {
        'cv_sync_timestamp_ms': cv_spike_t,
        'sensor_mode': sensor_mode,
        'sensor_left_sync_timestamp_ms': left_spike,
        'sensor_right_sync_timestamp_ms': right_spike,
    }

    if cv_spike_t is not None and left_spike is not None:
        result['offset_left_ms'] = left_spike - cv_spike_t
    if cv_spike_t is not None and right_spike is not None:
        result['offset_right_ms'] = right_spike - cv_spike_t
    if 'offset_left_ms' in result and 'offset_right_ms' in result:
        result['delta_lr_ms'] = abs(result['offset_left_ms'] - result['offset_right_ms'])

    with open(args.out, 'w') as f:
        json.dump(result, f, indent=2)

    print(f"Wrote {args.out}")


if __name__ == '__main__':
    main()
