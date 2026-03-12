from __future__ import annotations

import csv
import json
import shutil
import logging
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from api.core.settings import settings

logger = logging.getLogger("signglove.dataset_service")

# --- Constants & Schemas ---

SCHEMA_DIM_MAP = {
    "cv_single": 63,
    "cv_dual": 126,
    "sensor_single": 11,
    "sensor_dual": 22,
    "fusion_single": 74,
    "fusion_dual": 148,
}

LEGACY_SINGLE_SENSOR_ALIASES = {
    "f1": ("flex1",),
    "f2": ("flex2",),
    "f3": ("flex3",),
    "f4": ("flex4",),
    "f5": ("flex5",),
    "ax": ("accel_x",),
    "ay": ("accel_y",),
    "az": ("accel_z",),
    "gx": ("gyro_x",),
    "gy": ("gyro_y",),
    "gz": ("gyro_z",),
    "label": ("recording_label",),
}

# --- Internal Helpers ---

def _normalize_header(header: Optional[List[str]]) -> List[str]:
    if not header:
        return []
    return [str(h).strip() for h in header if h and str(h).strip()]

def _count_landmark_dims(columns: set[str], prefix: str) -> int:
    dim = 0
    for i in range(21):
        if f"{prefix}_x{i}" in columns: dim += 1
        if f"{prefix}_y{i}" in columns: dim += 1
        if f"{prefix}_z{i}" in columns: dim += 1
    return dim

def _get_present_name(columns: set[str], canonical: str, aliases: Tuple[str, ...] = ()) -> Optional[str]:
    if canonical in columns:
        return canonical
    for alias in aliases:
        if alias in columns:
            return alias
    return None

def _has_all_sensor_single(columns: set[str]) -> Tuple[bool, bool]:
    used_alias = False
    for canonical, aliases in LEGACY_SINGLE_SENSOR_ALIASES.items():
        present = _get_present_name(columns, canonical, aliases)
        if canonical == "label": continue
        if present is None: return False, used_alias
        if present != canonical: used_alias = True
    return True, used_alias

def _detect_schema_id(header: List[str]) -> str:
    columns = {h.strip() for h in header}
    sensor_single = {"f1", "f2", "f3", "f4", "f5", "ax", "ay", "az", "gx", "gy", "gz"}
    sensor_dual = {
        "left_flex_1", "left_flex_2", "left_flex_3", "left_flex_4", "left_flex_5",
        "left_acc_1", "left_acc_2", "left_acc_3", "left_gyro_1", "left_gyro_2", "left_gyro_3",
        "right_flex_1", "right_flex_2", "right_flex_3", "right_flex_4", "right_flex_5",
        "right_acc_1", "right_acc_2", "right_acc_3", "right_gyro_1", "right_gyro_2", "right_gyro_3",
    }
    has_sensor_prefixed = any(col.startswith("sensor_") for col in columns)
    has_cv = any(col.startswith("L_x") or col.startswith("R_x") for col in columns)

    if has_sensor_prefixed and has_cv:
        if any(col.startswith("sensor_left_") or col.startswith("sensor_right_") for col in columns):
            return "fusion_dual"
        if all(f"sensor_{col}" in columns for col in sensor_single):
            return "fusion_single"
        return "unknown"
    if all(col in columns for col in sensor_dual): return "sensor_dual"
    has_ss, _ = _has_all_sensor_single(columns)
    if has_ss or all(col in columns for col in sensor_single): return "sensor_single"
    left_dim = _count_landmark_dims(columns, "L")
    right_dim = _count_landmark_dims(columns, "R")
    if left_dim == 63 and right_dim == 63: return "cv_dual"
    if left_dim == 63 or right_dim == 63: return "cv_single"
    return "unknown"

class DatasetService:
    def __init__(self):
        self.data_dir = Path(settings.DATA_DIR)
        self.library_dir = self.data_dir / "csv_library"
        self.active_dir = self.library_dir / "active"
        self.archive_dir = self.library_dir / "archive"
        self.selection_file = self.library_dir / "selected_datasets.json"
        self.order_file = self.library_dir / "order.json"
        self._ensure_dirs()

    def _ensure_dirs(self):
        self.active_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)

    def get_roots(self, include_archived: bool = False) -> List[Tuple[str, Path]]:
        roots = [("active", self.active_dir)]
        if include_archived: roots.append(("archive", self.archive_dir))
        if self.data_dir.exists(): roots.append(("legacy", self.data_dir))
        return roots

    def resolve_csv_path(self, name: str, include_archived: bool = True) -> Tuple[str, Path, str]:
        val = (name or "").strip().replace("\\", "/")
        p = Path(val)
        if p.is_absolute() or ".." in p.parts:
            raise ValueError("Invalid filename path")
        
        for scope, root in self.get_roots(include_archived):
            candidate = (root / p).resolve()
            if candidate.exists() and candidate.is_file():
                return scope, candidate, val
        raise FileNotFoundError(f"CSV {val} not found")

    def scan_csv_file(self, path: Path) -> Dict[str, Any]:
        try:
            with path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
                reader = csv.DictReader(f)
                header = _normalize_header(reader.fieldnames)
                if not header: return {"status": "empty"}
                
                row_count = 0
                labels = Counter()
                for row in reader:
                    row_count += 1
                    lbl = row.get("label")
                    if lbl: labels[str(lbl)] += 1
                
                schema_id = _detect_schema_id(header)
                modality = "unknown"
                hand_mode = "unknown"
                if schema_id != "unknown":
                    parts = schema_id.split("_", 1)
                    modality = parts[0]
                    hand_mode = parts[1]

                return {
                    "columns": header,
                    "row_count": row_count,
                    "label_summary": [{"label": k, "count": v} for k, v in labels.items()],
                    "schema_id": schema_id,
                    "modality": modality,
                    "hand_mode": hand_mode,
                    "expected_feature_dim": SCHEMA_DIM_MAP.get(schema_id),
                    "schema_version": "v1",
                    "health_flags": [] if schema_id != "unknown" else ["unknown_schema"]
                }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # --- Storage & Selection ---

    def load_selection_store(self) -> Dict[str, Dict[str, Any]]:
        if not self.selection_file.exists(): return {}
        try:
            with self.selection_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception: return {}

    def save_selection_store(self, data: Dict[str, Dict[str, Any]]):
        tmp = self.selection_file.with_suffix(".json.tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=True, indent=2)
        tmp.replace(self.selection_file)

    def load_order_store(self) -> List[str]:
        if not self.order_file.exists(): return []
        try:
            with self.order_file.open("r", encoding="utf-8") as f:
                data = json.load(f)
            return [str(x).strip() for x in data if x] if isinstance(data, list) else []
        except Exception: return []

    def save_order_store(self, data: List[str]):
        tmp = self.order_file.with_suffix(".json.tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=True, indent=2)
        tmp.replace(self.order_file)

    # --- Sidecar Metadata ---

    def sidecar_path(self, csv_path: Path) -> Path:
        return csv_path.with_suffix(".metadata.json")

    def load_sidecar(self, csv_path: Path) -> Dict[str, Any]:
        p = self.sidecar_path(csv_path)
        if not p.exists(): return {}
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception: return {}

    def save_sidecar(self, csv_path: Path, data: Dict[str, Any]):
        p = self.sidecar_path(csv_path)
        p.write_text(json.dumps(data, ensure_ascii=True, indent=2), encoding="utf-8")

    def trigger_scan(self, csv_name: str, include_archived: bool = True) -> str:
        """Triggers a background scan task and returns the job ID."""
        from workers.tasks.dataset_tasks import scan_dataset_task
        task = scan_dataset_task.delay(csv_name, include_archived)
        return task.id

dataset_service = DatasetService()
