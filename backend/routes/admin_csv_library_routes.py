from __future__ import annotations

import csv
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import shutil
import json
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from core.settings import settings
from routes.auth_routes import role_or_internal_dep

router = APIRouter(prefix="/admin/csv-library", tags=["Admin CSV Library"])

MAX_PREVIEW_LIMIT = 500
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


class DatasetSelectionRequest(BaseModel):
    name: str
    pipeline: str = "early"
    mode: str = "single"
    modality: Optional[str] = None


class DeleteCsvRequest(BaseModel):
    confirm_name: str


def _safe_csv_name(name: str) -> str:
    value = (name or "").strip().replace("\\", "/")
    if not value:
        raise HTTPException(status_code=400, detail="Filename is required")
    p = Path(value)
    if p.is_absolute() or ".." in p.parts:
        raise HTTPException(status_code=400, detail="Invalid filename path")
    if p.suffix.lower() != ".csv":
        raise HTTPException(status_code=400, detail="Only .csv files are allowed")
    return str(p)


def _active_root() -> Path:
    return Path(settings.DATA_DIR) / "csv_library" / "active"


def _archive_root() -> Path:
    return Path(settings.DATA_DIR) / "csv_library" / "archive"


def _selection_store_path() -> Path:
    return Path(settings.DATA_DIR) / "csv_library" / "selected_datasets.json"


def _legacy_root() -> Path:
    return Path(settings.DATA_DIR)


def _list_roots(include_archived: bool = False) -> List[Tuple[str, Path]]:
    roots: List[Tuple[str, Path]] = []

    active = _active_root()
    if active.exists():
        roots.append(("active", active))

    if include_archived:
        archive = _archive_root()
        if archive.exists():
            roots.append(("archive", archive))

    # Backward compatibility for existing datasets currently under backend/data/*.csv.
    legacy = _legacy_root()
    if legacy.exists():
        roots.append(("legacy", legacy))

    return roots


def _normalize_header(header: Optional[List[str]]) -> List[str]:
    if not header:
        return []
    return [str(h).strip() for h in header if h and str(h).strip()]


def _timestamp_to_millis(raw: Any) -> Optional[int]:
    if raw is None or raw == "":
        return None
    try:
        return int(float(str(raw)))
    except (TypeError, ValueError):
        return None


def _count_landmark_dims(columns: set[str], prefix: str) -> int:
    dim = 0
    for i in range(21):
        if f"{prefix}_x{i}" in columns:
            dim += 1
        if f"{prefix}_y{i}" in columns:
            dim += 1
        if f"{prefix}_z{i}" in columns:
            dim += 1
    return dim


def _get_present_name(columns: set[str], canonical: str, aliases: Tuple[str, ...] = ()) -> Optional[str]:
    if canonical in columns:
        return canonical
    for alias in aliases:
        if alias in columns:
            return alias
    return None


def _build_legacy_rename_map(columns: set[str]) -> Dict[str, str]:
    rename_map: Dict[str, str] = {}
    for canonical, aliases in LEGACY_SINGLE_SENSOR_ALIASES.items():
        for alias in aliases:
            if alias in columns:
                rename_map[alias] = canonical
                break
    return rename_map


def _has_all_sensor_single(columns: set[str]) -> Tuple[bool, bool]:
    used_alias = False
    for canonical, aliases in LEGACY_SINGLE_SENSOR_ALIASES.items():
        present = _get_present_name(columns, canonical, aliases)
        if canonical == "label":
            # label is recommended but not required for structural sensor schema detection
            continue
        if present is None:
            return False, used_alias
        if present != canonical:
            used_alias = True
    return True, used_alias


def _detect_schema_id(header: List[str]) -> str:
    columns = {h.strip() for h in header}

    sensor_single = {"f1", "f2", "f3", "f4", "f5", "ax", "ay", "az", "gx", "gy", "gz"}
    sensor_dual = {
        "left_flex_1", "left_flex_2", "left_flex_3", "left_flex_4", "left_flex_5",
        "left_acc_1", "left_acc_2", "left_acc_3",
        "left_gyro_1", "left_gyro_2", "left_gyro_3",
        "right_flex_1", "right_flex_2", "right_flex_3", "right_flex_4", "right_flex_5",
        "right_acc_1", "right_acc_2", "right_acc_3",
        "right_gyro_1", "right_gyro_2", "right_gyro_3",
    }

    has_sensor_prefixed = any(col.startswith("sensor_") for col in columns)
    has_cv = any(col.startswith("L_x") or col.startswith("R_x") for col in columns)

    if has_sensor_prefixed and has_cv:
        if any(col.startswith("sensor_left_") or col.startswith("sensor_right_") for col in columns):
            return "fusion_dual"
        if all(f"sensor_{col}" in columns for col in sensor_single):
            return "fusion_single"
        return "unknown"

    if all(col in columns for col in sensor_dual):
        return "sensor_dual"
    has_sensor_single, _used_alias = _has_all_sensor_single(columns)
    if has_sensor_single or all(col in columns for col in sensor_single):
        return "sensor_single"

    left_dim = _count_landmark_dims(columns, "L")
    right_dim = _count_landmark_dims(columns, "R")
    if left_dim == 63 and right_dim == 63:
        return "cv_dual"
    if left_dim == 63 or right_dim == 63:
        return "cv_single"

    return "unknown"


def _compute_actual_feature_dim(schema_id: str, header: List[str]) -> Optional[int]:
    columns = {h.strip() for h in header}

    if schema_id == "cv_single":
        return 63
    if schema_id == "cv_dual":
        return _count_landmark_dims(columns, "L") + _count_landmark_dims(columns, "R")

    if schema_id == "sensor_single":
        sensor_single = ["f1", "f2", "f3", "f4", "f5", "ax", "ay", "az", "gx", "gy", "gz"]
        dim = 0
        for canonical in sensor_single:
            aliases = LEGACY_SINGLE_SENSOR_ALIASES.get(canonical, ())
            if _get_present_name(columns, canonical, aliases) is not None:
                dim += 1
        return dim

    if schema_id == "sensor_dual":
        sensor_dual = [
            "left_flex_1", "left_flex_2", "left_flex_3", "left_flex_4", "left_flex_5",
            "left_acc_1", "left_acc_2", "left_acc_3", "left_gyro_1", "left_gyro_2", "left_gyro_3",
            "right_flex_1", "right_flex_2", "right_flex_3", "right_flex_4", "right_flex_5",
            "right_acc_1", "right_acc_2", "right_acc_3", "right_gyro_1", "right_gyro_2", "right_gyro_3",
        ]
        return sum(1 for c in sensor_dual if c in columns)

    if schema_id.startswith("fusion_"):
        sensor_dim = 0
        if schema_id == "fusion_single":
            sensor_single = ["sensor_f1", "sensor_f2", "sensor_f3", "sensor_f4", "sensor_f5", "sensor_ax", "sensor_ay", "sensor_az", "sensor_gx", "sensor_gy", "sensor_gz"]
            sensor_dim = sum(1 for c in sensor_single if c in columns)
        elif schema_id == "fusion_dual":
            sensor_dual = [
                "sensor_left_flex_1", "sensor_left_flex_2", "sensor_left_flex_3", "sensor_left_flex_4", "sensor_left_flex_5",
                "sensor_left_acc_1", "sensor_left_acc_2", "sensor_left_acc_3", "sensor_left_gyro_1", "sensor_left_gyro_2", "sensor_left_gyro_3",
                "sensor_right_flex_1", "sensor_right_flex_2", "sensor_right_flex_3", "sensor_right_flex_4", "sensor_right_flex_5",
                "sensor_right_acc_1", "sensor_right_acc_2", "sensor_right_acc_3", "sensor_right_gyro_1", "sensor_right_gyro_2", "sensor_right_gyro_3",
            ]
            sensor_dim = sum(1 for c in sensor_dual if c in columns)

        vision_dim = _count_landmark_dims(columns, "L") + _count_landmark_dims(columns, "R")
        return sensor_dim + vision_dim

    return None


def _derive_modality_and_mode(schema_id: str) -> Tuple[str, str]:
    if schema_id == "unknown":
        return "unknown", "unknown"
    modality, hand_mode = schema_id.split("_", 1)
    return modality, hand_mode


def _scan_csv_file(path: Path) -> Dict[str, Any]:
    header: List[str] = []
    row_count = 0
    labels = Counter()
    ts_values: List[int] = []
    health_flags: List[str] = []

    try:
        with path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
            reader = csv.DictReader(f)
            header = _normalize_header(reader.fieldnames)
            if not header:
                return {
                    "columns": [],
                    "row_count": 0,
                    "label_summary": [],
                    "timestamp_range": {"start_ms": None, "end_ms": None},
                    "health_flags": ["empty_file", "missing_required_columns", "unknown_schema"],
                    "schema_id": "unknown",
                    "schema_version": "v1",
                    "modality": "unknown",
                    "hand_mode": "unknown",
                    "expected_feature_dim": None,
                    "actual_feature_dim": None,
                }

            for row in reader:
                row_count += 1
                label = row.get("label")
                if label not in (None, ""):
                    labels[str(label)] += 1

                ts = _timestamp_to_millis(row.get("timestamp_ms"))
                if ts is not None:
                    ts_values.append(ts)

    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to parse CSV '{path.name}': {exc}")

    schema_id = _detect_schema_id(header)
    columns_set = {h.strip() for h in header}
    legacy_rename_map = _build_legacy_rename_map(columns_set)
    has_sensor_single, used_sensor_single_alias = _has_all_sensor_single(columns_set)
    modality, hand_mode = _derive_modality_and_mode(schema_id)
    expected_dim = SCHEMA_DIM_MAP.get(schema_id)
    actual_dim = _compute_actual_feature_dim(schema_id, header)

    if row_count == 0:
        health_flags.append("empty_file")
    if schema_id == "unknown":
        health_flags.append("unknown_schema")
    if schema_id == "sensor_single" and has_sensor_single and used_sensor_single_alias:
        health_flags.append("schema_mapped_from_legacy")
    if "timestamp_ms" not in header:
        health_flags.append("missing_required_columns")
    if ts_values and len(ts_values) != len(set(ts_values)):
        health_flags.append("duplicate_timestamps")
    if any(ts_values[i] > ts_values[i + 1] for i in range(len(ts_values) - 1)):
        health_flags.append("timestamp_not_monotonic")
    if expected_dim is not None and actual_dim is not None and expected_dim != actual_dim:
        health_flags.append("feature_dim_mismatch")
        health_flags.append("schema_mismatch")

    ts_start = min(ts_values) if ts_values else None
    ts_end = max(ts_values) if ts_values else None

    return {
        "columns": header,
        "row_count": row_count,
        "label_summary": [{"label": k, "count": v} for k, v in labels.most_common(10)],
        "timestamp_range": {"start_ms": ts_start, "end_ms": ts_end},
        "health_flags": sorted(set(health_flags)),
        "schema_id": schema_id,
        "schema_version": "v1",
        "modality": modality,
        "hand_mode": hand_mode,
        "expected_feature_dim": expected_dim,
        "actual_feature_dim": actual_dim,
        "legacy_rename_map": legacy_rename_map,
    }


def _compatible_schema_ids(pipeline: str, mode: str) -> List[str]:
    if pipeline == "early":
        return ["fusion_single"] if mode == "single" else ["fusion_dual"]
    if pipeline == "late":
        if mode == "single":
            return ["cv_single", "sensor_single"]
        return ["cv_dual", "sensor_dual"]
    return []


def _late_expected_schema(mode: str, modality: str) -> Optional[str]:
    if mode not in {"single", "dual"}:
        return None
    if modality not in {"cv", "sensor"}:
        return None
    return f"{modality}_{mode}"


def _selection_key(pipeline: str, mode: str, modality: Optional[str] = None) -> str:
    if pipeline == "late":
        if modality not in {"cv", "sensor"}:
            raise HTTPException(status_code=400, detail="modality is required for late pipeline selection")
        return f"{pipeline}:{mode}:{modality}"
    return f"{pipeline}:{mode}"


def _load_selection_store() -> Dict[str, Dict[str, Any]]:
    path = _selection_store_path()
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        return data
    except Exception:
        return {}


def _save_selection_store(data: Dict[str, Dict[str, Any]]) -> None:
    path = _selection_store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".json.tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=True, indent=2)
    tmp_path.replace(path)

def _sensor_single_required_columns() -> List[str]:
    return ["timestamp_ms", "f1", "f2", "f3", "f4", "f5", "ax", "ay", "az", "gx", "gy", "gz"]


def _sensor_dual_required_columns() -> List[str]:
    return [
        "timestamp_ms",
        "left_flex_1", "left_flex_2", "left_flex_3", "left_flex_4", "left_flex_5",
        "left_acc_1", "left_acc_2", "left_acc_3", "left_gyro_1", "left_gyro_2", "left_gyro_3",
        "right_flex_1", "right_flex_2", "right_flex_3", "right_flex_4", "right_flex_5",
        "right_acc_1", "right_acc_2", "right_acc_3", "right_gyro_1", "right_gyro_2", "right_gyro_3",
    ]


def _compute_schema_mismatch_details(schema_id: str, header: List[str]) -> Dict[str, Any]:
    columns = {h.strip() for h in header}
    missing_required_columns: List[str] = []
    notes: List[str] = []

    if schema_id == "sensor_single":
        for canonical in _sensor_single_required_columns():
            aliases = LEGACY_SINGLE_SENSOR_ALIASES.get(canonical, ())
            if _get_present_name(columns, canonical, aliases) is None:
                missing_required_columns.append(canonical)
    elif schema_id == "sensor_dual":
        missing_required_columns = [c for c in _sensor_dual_required_columns() if c not in columns]
    elif schema_id == "cv_single":
        has_left = _count_landmark_dims(columns, "L") == 63
        has_right = _count_landmark_dims(columns, "R") == 63
        if "timestamp_ms" not in columns:
            missing_required_columns.append("timestamp_ms")
        if not (has_left or has_right):
            notes.append("Expected one full hand landmark set (L_* or R_*) with 63 dims.")
    elif schema_id == "cv_dual":
        if "timestamp_ms" not in columns:
            missing_required_columns.append("timestamp_ms")
        if _count_landmark_dims(columns, "L") != 63:
            notes.append("Left hand landmark dimensions are incomplete.")
        if _count_landmark_dims(columns, "R") != 63:
            notes.append("Right hand landmark dimensions are incomplete.")
    elif schema_id == "fusion_single":
        sensor_required = [f"sensor_{c}" for c in _sensor_single_required_columns() if c != "timestamp_ms"]
        missing_required_columns.extend([c for c in ["timestamp_ms", *sensor_required] if c not in columns])
        has_left = _count_landmark_dims(columns, "L") == 63
        has_right = _count_landmark_dims(columns, "R") == 63
        if not (has_left or has_right):
            notes.append("Expected one full hand landmark set for fusion_single.")
    elif schema_id == "fusion_dual":
        sensor_required = [
            "sensor_left_flex_1", "sensor_left_flex_2", "sensor_left_flex_3", "sensor_left_flex_4", "sensor_left_flex_5",
            "sensor_left_acc_1", "sensor_left_acc_2", "sensor_left_acc_3", "sensor_left_gyro_1", "sensor_left_gyro_2", "sensor_left_gyro_3",
            "sensor_right_flex_1", "sensor_right_flex_2", "sensor_right_flex_3", "sensor_right_flex_4", "sensor_right_flex_5",
            "sensor_right_acc_1", "sensor_right_acc_2", "sensor_right_acc_3", "sensor_right_gyro_1", "sensor_right_gyro_2", "sensor_right_gyro_3",
        ]
        missing_required_columns.extend([c for c in ["timestamp_ms", *sensor_required] if c not in columns])
        if _count_landmark_dims(columns, "L") != 63:
            notes.append("Left hand landmark dimensions are incomplete for fusion_dual.")
        if _count_landmark_dims(columns, "R") != 63:
            notes.append("Right hand landmark dimensions are incomplete for fusion_dual.")
    else:
        notes.append("Unknown schema; cannot determine required column set.")

    return {
        "missing_required_columns": missing_required_columns,
        "notes": notes,
    }


def _compute_csv_stats(path: Path, meta: Dict[str, Any]) -> Dict[str, Any]:
    header = meta.get("columns", [])
    schema_id = meta.get("schema_id", "unknown")
    schema_details = _compute_schema_mismatch_details(schema_id, header)

    row_count = 0
    missing_values_count = 0
    timestamp_values: List[int] = []
    label_counter = Counter()

    try:
        with path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                row_count += 1
                for value in row.values():
                    if value is None or str(value).strip() == "":
                        missing_values_count += 1

                label = row.get("label")
                if not label:
                    label = row.get("recording_label")
                if label:
                    label_counter[str(label)] += 1

                ts = _timestamp_to_millis(row.get("timestamp_ms"))
                if ts is not None:
                    timestamp_values.append(ts)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to compute stats for '{path.name}': {exc}")

    duplicate_timestamp_count = max(0, len(timestamp_values) - len(set(timestamp_values)))
    timestamp_range = {
        "start_ms": min(timestamp_values) if timestamp_values else None,
        "end_ms": max(timestamp_values) if timestamp_values else None,
    }
    health_flags = set(meta.get("health_flags", []))
    if schema_details["missing_required_columns"]:
        health_flags.add("missing_required_columns")

    return {
        "row_count": row_count,
        "column_count": len(header),
        "schema_id": schema_id,
        "schema_version": meta.get("schema_version", "v1"),
        "expected_feature_dim": meta.get("expected_feature_dim"),
        "actual_feature_dim": meta.get("actual_feature_dim"),
        "missing_values_count": missing_values_count,
        "duplicate_timestamp_count": duplicate_timestamp_count,
        "label_distribution": [{"label": k, "count": v} for k, v in label_counter.most_common(50)],
        "timestamp_range": timestamp_range,
        "schema_mismatch_details": schema_details,
        "health_flags": sorted(health_flags),
    }


def _collect_csv_paths(include_archived: bool = False) -> List[Tuple[str, Path, str]]:
    files: List[Tuple[str, Path, str]] = []
    for scope, root in _list_roots(include_archived=include_archived):
        if not root.exists():
            continue
        for path in root.rglob("*.csv"):
            if not path.is_file():
                continue
            if scope == "legacy":
                try:
                    rel_to_legacy = path.relative_to(root).parts
                except ValueError:
                    rel_to_legacy = ()
                # Avoid duplicate discovery for files managed under csv_library/* roots.
                if rel_to_legacy and rel_to_legacy[0] == "csv_library":
                    continue
            rel_name = str(path.relative_to(root)).replace("\\", "/")
            files.append((scope, path, rel_name))
    return files


def _resolve_csv_path(name: str, include_archived: bool = True) -> Tuple[str, Path, str]:
    safe_name = _safe_csv_name(name)
    for scope, root in _list_roots(include_archived=include_archived):
        candidate = (root / safe_name).resolve()
        try:
            candidate.relative_to(root.resolve())
        except ValueError:
            continue
        if candidate.exists() and candidate.is_file():
            return scope, candidate, safe_name

    raise HTTPException(status_code=404, detail=f"CSV file not found: {safe_name}")


def _archive_target_path(schema_id: str, original_name: str) -> Path:
    safe_schema_id = schema_id if schema_id in SCHEMA_DIM_MAP else "unknown"
    target_root = _archive_root() / safe_schema_id
    target_root.mkdir(parents=True, exist_ok=True)
    candidate = target_root / Path(original_name).name
    if not candidate.exists():
        return candidate

    stem = candidate.stem
    suffix = candidate.suffix
    for i in range(1, 10_000):
        next_candidate = target_root / f"{stem}__archived_{i}{suffix}"
        if not next_candidate.exists():
            return next_candidate
    raise HTTPException(status_code=500, detail="Unable to allocate archive filename")


def _sidecar_metadata_path(csv_path: Path) -> Path:
    return csv_path.with_suffix(".metadata.json")


def _load_sidecar_metadata(csv_path: Path) -> Dict[str, Any]:
    sidecar = _sidecar_metadata_path(csv_path)
    if not sidecar.exists() or not sidecar.is_file():
        return {}
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _with_worker_metadata(base: Dict[str, Any], csv_path: Path) -> Dict[str, Any]:
    sidecar = _load_sidecar_metadata(csv_path)
    if not sidecar:
        base["worker_validation"] = None
        return base

    worker_validation = sidecar.get("validation") if isinstance(sidecar.get("validation"), dict) else None
    sidecar_flags = sidecar.get("health_flags") if isinstance(sidecar.get("health_flags"), list) else []
    merged_flags = sorted(set(list(base.get("health_flags", [])) + [str(flag) for flag in sidecar_flags if isinstance(flag, str)]))
    base["health_flags"] = merged_flags
    base["worker_validation"] = worker_validation
    base["worker_job_id"] = sidecar.get("job_id")
    base["worker_processed_at"] = sidecar.get("processed_at")
    return base


@router.get("/files")
async def list_csv_files(
    include_archived: bool = Query(False),
    _user=Depends(role_or_internal_dep("admin")),
):
    result: List[Dict[str, Any]] = []
    for scope, path, rel_name in _collect_csv_paths(include_archived=include_archived):
        stat = path.stat()
        meta = _scan_csv_file(path)
        result.append(
            _with_worker_metadata({
                "name": rel_name,
                "scope": scope,
                "size_bytes": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                "schema_id": meta["schema_id"],
                "schema_version": meta["schema_version"],
                "modality": meta["modality"],
                "hand_mode": meta["hand_mode"],
                "feature_dim": meta["expected_feature_dim"],
                "row_count": meta["row_count"],
                "columns": meta["columns"],
                "label_summary": meta["label_summary"],
                "timestamp_range": meta["timestamp_range"],
                "health_flags": meta["health_flags"],
            }, path)
        )

    result.sort(key=lambda item: (item.get("schema_id") or "", item.get("modified_at") or ""), reverse=False)
    return {"status": "success", "files": result}


@router.get("/compatible")
async def list_compatible_csv_files(
    pipeline: str = Query("early", pattern="^(early|late)$"),
    mode: str = Query("single", pattern="^(single|dual)$"),
    include_archived: bool = Query(False),
    _user=Depends(role_or_internal_dep("admin")),
):
    allowed = set(_compatible_schema_ids(pipeline, mode))
    result: List[Dict[str, Any]] = []

    for scope, path, rel_name in _collect_csv_paths(include_archived=include_archived):
        stat = path.stat()
        meta = _scan_csv_file(path)
        if meta.get("schema_id") not in allowed:
            continue
        result.append(
            _with_worker_metadata({
                "name": rel_name,
                "scope": scope,
                "size_bytes": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                "schema_id": meta["schema_id"],
                "schema_version": meta["schema_version"],
                "modality": meta["modality"],
                "hand_mode": meta["hand_mode"],
                "feature_dim": meta["expected_feature_dim"],
                "row_count": meta["row_count"],
                "columns": meta["columns"],
                "label_summary": meta["label_summary"],
                "timestamp_range": meta["timestamp_range"],
                "health_flags": meta["health_flags"],
            }, path)
        )

    result.sort(key=lambda item: (item.get("schema_id") or "", item.get("modified_at") or ""), reverse=False)
    return {
        "status": "success",
        "pipeline": pipeline,
        "mode": mode,
        "compatible_schema_ids": sorted(allowed),
        "files": result,
    }


@router.get("/selection")
async def get_selected_dataset(
    pipeline: str = Query("early", pattern="^(early|late)$"),
    mode: str = Query("single", pattern="^(single|dual)$"),
    modality: Optional[str] = Query(None, pattern="^(cv|sensor)$"),
    _user=Depends(role_or_internal_dep("admin")),
):
    store = _load_selection_store()
    if pipeline == "late" and modality is None:
        key_cv = _selection_key(pipeline, mode, "cv")
        key_sensor = _selection_key(pipeline, mode, "sensor")
        selected_cv = store.get(key_cv)
        selected_sensor = store.get(key_sensor)
        return {
            "status": "success",
            "pipeline": pipeline,
            "mode": mode,
            "selection": {
                "cv": selected_cv,
                "sensor": selected_sensor,
                "is_complete_pair": bool(selected_cv and selected_sensor),
            },
        }

    key = _selection_key(pipeline, mode, modality)
    selected = store.get(key)
    return {
        "status": "success",
        "pipeline": pipeline,
        "mode": mode,
        "modality": modality,
        "selection": selected,
    }


@router.get("/selection/all")
async def get_all_selected_datasets(
    _user=Depends(role_or_internal_dep("admin")),
):
    store = _load_selection_store()
    return {
        "status": "success",
        "selections": store,
    }


@router.post("/selection")
async def set_selected_dataset(
    req: DatasetSelectionRequest,
    _user=Depends(role_or_internal_dep("admin")),
):
    pipeline = (req.pipeline or "").strip().lower()
    mode = (req.mode or "").strip().lower()
    modality = (req.modality or "").strip().lower() or None
    if pipeline not in {"early", "late"}:
        raise HTTPException(status_code=400, detail="pipeline must be 'early' or 'late'")
    if mode not in {"single", "dual"}:
        raise HTTPException(status_code=400, detail="mode must be 'single' or 'dual'")

    scope, path, safe_name = _resolve_csv_path(req.name, include_archived=True)
    meta = _scan_csv_file(path)
    allowed = set(_compatible_schema_ids(pipeline, mode))
    schema_id = meta.get("schema_id", "unknown")
    if pipeline == "late":
        if modality not in {"cv", "sensor"}:
            raise HTTPException(status_code=400, detail="modality must be provided for late pipeline selection (cv|sensor)")
        expected_schema = _late_expected_schema(mode, modality)
        if schema_id != expected_schema:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Late selection expects schema_id '{expected_schema}' for modality='{modality}', "
                    f"but got '{schema_id}'"
                ),
            )
    else:
        if schema_id not in allowed:
            raise HTTPException(
                status_code=400,
                detail=f"schema_id '{schema_id}' is not compatible with pipeline={pipeline}, mode={mode}",
            )

    key = _selection_key(pipeline, mode, modality)
    store = _load_selection_store()
    selected_at = datetime.now(timezone.utc).isoformat()
    store[key] = {
        "name": safe_name,
        "scope": scope,
        "schema_id": schema_id,
        "pipeline": pipeline,
        "mode": mode,
        "modality": modality,
        "selected_at": selected_at,
    }
    _save_selection_store(store)
    return {
        "status": "success",
        "key": key,
        "selection": store[key],
    }


@router.get("/files/{name:path}/preview")
async def preview_csv_file(
    name: str,
    limit: int = Query(100, ge=1, le=MAX_PREVIEW_LIMIT),
    offset: int = Query(0, ge=0),
    _user=Depends(role_or_internal_dep("admin")),
):
    scope, path, safe_name = _resolve_csv_path(name, include_archived=True)
    meta = _scan_csv_file(path)

    rows: List[Dict[str, Any]] = []
    total_rows = 0
    try:
        with path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
            reader = csv.DictReader(f)
            for idx, row in enumerate(reader):
                total_rows += 1
                if idx < offset:
                    continue
                if len(rows) >= limit:
                    continue
                rows.append({k: ("" if v is None else str(v)) for k, v in row.items()})
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to preview CSV '{safe_name}': {exc}")

    schema_check = "pass" if "schema_mismatch" not in meta["health_flags"] and "unknown_schema" not in meta["health_flags"] else "fail"

    return _with_worker_metadata({
        "status": "success",
        "name": safe_name,
        "scope": scope,
        "header": meta["columns"],
        "rows": rows,
        "total_rows": total_rows,
        "limit": limit,
        "offset": offset,
        "schema_id": meta["schema_id"],
        "schema_version": meta["schema_version"],
        "schema_check": schema_check,
        "health_flags": meta["health_flags"],
    }, path)


@router.get("/files/{name:path}/download")
async def download_csv_file(
    name: str,
    _user=Depends(role_or_internal_dep("admin")),
):
    _scope, path, safe_name = _resolve_csv_path(name, include_archived=True)
    return FileResponse(
        path=str(path),
        media_type="text/csv",
        filename=Path(safe_name).name,
    )


@router.get("/files/{name:path}/compatibility")
async def csv_file_compatibility(
    name: str,
    pipeline: str = Query("early", pattern="^(early|late)$"),
    mode: str = Query("single", pattern="^(single|dual)$"),
    _user=Depends(role_or_internal_dep("admin")),
):
    scope, path, safe_name = _resolve_csv_path(name, include_archived=True)
    meta = _scan_csv_file(path)
    allowed = _compatible_schema_ids(pipeline, mode)
    is_compatible = meta["schema_id"] in allowed

    reason = (
        "compatible"
        if is_compatible
        else f"schema_id '{meta['schema_id']}' is not valid for pipeline={pipeline}, mode={mode}"
    )

    return {
        "status": "success",
        "name": safe_name,
        "scope": scope,
        "pipeline": pipeline,
        "mode": mode,
        "schema_id": meta["schema_id"],
        "compatible_schema_ids": allowed,
        "is_compatible": is_compatible,
        "reason": reason,
        "legacy_rename_map": meta.get("legacy_rename_map", {}),
    }


@router.get("/files/{name:path}/stats")
async def csv_file_stats(
    name: str,
    _user=Depends(role_or_internal_dep("admin")),
):
    scope, path, safe_name = _resolve_csv_path(name, include_archived=True)
    meta = _scan_csv_file(path)
    stats = _compute_csv_stats(path, meta)
    return _with_worker_metadata({
        "status": "success",
        "name": safe_name,
        "scope": scope,
        **stats,
    }, path)


@router.post("/files/{name:path}/archive")
async def archive_csv_file(
    name: str,
    _user=Depends(role_or_internal_dep("admin")),
):
    scope, path, safe_name = _resolve_csv_path(name, include_archived=True)
    if scope == "archive":
        raise HTTPException(status_code=400, detail="File is already archived")

    meta = _scan_csv_file(path)
    destination = _archive_target_path(meta.get("schema_id", "unknown"), safe_name)
    destination.parent.mkdir(parents=True, exist_ok=True)

    try:
        shutil.move(str(path), str(destination))
        sidecar = _sidecar_metadata_path(path)
        if sidecar.exists() and sidecar.is_file():
            shutil.move(str(sidecar), str(_sidecar_metadata_path(destination)))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to archive file '{safe_name}': {exc}")

    archived_at = datetime.now(timezone.utc).isoformat()
    return {
        "status": "success",
        "name": safe_name,
        "from_path": str(path),
        "to_path": str(destination),
        "schema_id": meta.get("schema_id", "unknown"),
        "archived_at": archived_at,
    }


@router.delete("/files/{name:path}")
async def delete_csv_file_permanently(
    name: str,
    req: DeleteCsvRequest,
    _user=Depends(role_or_internal_dep("admin")),
):
    scope, path, safe_name = _resolve_csv_path(name, include_archived=True)
    expected = safe_name
    if req.confirm_name.strip() != expected:
        raise HTTPException(
            status_code=400,
            detail=f"Confirmation mismatch. Type exact file name: {expected}",
        )

    try:
        path.unlink()
        sidecar = _sidecar_metadata_path(path)
        if sidecar.exists() and sidecar.is_file():
            sidecar.unlink()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"CSV file not found: {safe_name}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to delete file '{safe_name}': {exc}")

    # Clean up selection slots that reference deleted file.
    store = _load_selection_store()
    keys_to_remove = [k for k, v in store.items() if isinstance(v, dict) and v.get("name") == safe_name]
    if keys_to_remove:
        for key in keys_to_remove:
            store.pop(key, None)
        _save_selection_store(store)

    return {
        "status": "success",
        "name": safe_name,
        "scope": scope,
        "deleted_at": datetime.now(timezone.utc).isoformat(),
        "selection_slots_cleared": keys_to_remove,
    }
