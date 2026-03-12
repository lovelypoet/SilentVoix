import csv
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
from datetime import datetime, timezone

logger = logging.getLogger("signglove.fusion_service")

class FusionService:
    def __init__(self, csv_dir: Path):
        self.csv_dir = csv_dir

    def _load_csv(self, name: str) -> List[Dict[str, Any]]:
        path = self.csv_dir / name
        if not path.exists():
            raise FileNotFoundError(f"CSV not found: {name}")
        
        with open(path, "r", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def _get_timestamp(self, row: Dict[str, Any]) -> float:
        return float(row.get("timestamp") or 0)

    def interpolate_sensor_data(
        self, 
        cv_rows: List[Dict[str, Any]], 
        sensor_rows: List[Dict[str, Any]], 
        offset_ms: float,
        trim_in_pct: float,
        trim_out_pct: float,
        mode: str
    ) -> List[Dict[str, Any]]:
        """
        Merges CV and Sensor data using Linear Interpolation.
        CV acts as the 'Master Clock'.
        """
        if not cv_rows or not sensor_rows:
            return []

        # 1. Apply Offset to Sensor Timestamps
        # Positive offset means sensor data is shifted "later" in time
        s_data = []
        for r in sensor_rows:
            s_data.append({
                "ts": self._get_timestamp(r) + (offset_ms / 1000.0),
                "vals": r
            })

        # 2. Determine Trimming Window based on CV duration
        cv_start_ts = self._get_timestamp(cv_rows[0])
        cv_end_ts = self._get_timestamp(cv_rows[-1])
        cv_duration = cv_end_ts - cv_start_ts

        window_start = cv_start_ts + (cv_duration * (trim_in_pct / 100.0))
        window_end = cv_start_ts + (cv_duration * (trim_out_pct / 100.0))

        # 3. Filter CV rows to window
        active_cv = [r for r in cv_rows if window_start <= self._get_timestamp(r) <= window_end]
        
        # Identify sensor columns (exclude timestamp, etc)
        # We assume sensor models want: f1..f5, ax, ay, az, gx, gy, gz
        sensor_keys = [k for k in sensor_rows[0].keys() if k not in {"timestamp", "gesture_label", "device_id", "source"}]
        
        fused_rows = []
        s_idx = 0
        
        for cv_row in active_cv:
            t_target = self._get_timestamp(cv_row)
            
            # Find two sensor points S1 and S2 such that S1.ts <= t_target < S2.ts
            while s_idx < len(s_data) - 1 and s_data[s_idx+1]["ts"] < t_target:
                s_idx += 1
            
            if s_idx >= len(s_data) - 1:
                # Out of sensor data bounds, pad with last known or skip
                continue
                
            s1 = s_data[s_idx]
            s2 = s_data[s_idx+1]
            
            if s1["ts"] > t_target:
                # Target is before first sensor point
                continue

            # Linear Interpolation Factor (0.0 to 1.0)
            denom = s2["ts"] - s1["ts"]
            factor = (t_target - s1["ts"]) / denom if denom != 0 else 0
            
            # Create the Fused Row
            fused_row = cv_row.copy()
            
            for key in sensor_keys:
                try:
                    v1 = float(s1["vals"].get(key) or 0)
                    v2 = float(s2["vals"].get(key) or 0)
                    # Interpolate: v = v1 + (v2 - v1) * factor
                    fused_val = v1 + (v2 - v1) * factor
                    fused_row[f"sensor_{key}"] = round(fused_val, 6)
                except ValueError:
                    fused_row[f"sensor_{key}"] = s1["vals"].get(key)

            fused_rows.append(fused_row)

        return fused_rows

    def export_fusion(self, params: Dict[str, Any]) -> str:
        cv_name = params["cv_name"]
        sensor_name = params["sensor_name"]
        offset_ms = params.get("offset_ms", 0)
        trim_in = params.get("trim_in_pct", 0)
        trim_out = params.get("trim_out_pct", 100)
        mode = params.get("mode", "single")

        cv_rows = self._load_csv(cv_name)
        sensor_rows = self._load_csv(sensor_name)

        fused = self.interpolate_sensor_data(cv_rows, sensor_rows, offset_ms, trim_in, trim_out, mode)

        if not fused:
            raise ValueError("No data remained after alignment and trimming. Check offsets.")

        # Save to a new file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_name = f"fusion_{mode}_aligned_{timestamp}.csv"
        export_path = self.csv_dir / export_name

        with open(export_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fused[0].keys())
            writer.writeheader()
            writer.writerows(fused)

        return export_name

# Singleton instance
from api.core.settings import settings
fusion_service = FusionService(Path(settings.DATA_DIR) / "active")
