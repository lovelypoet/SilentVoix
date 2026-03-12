"""
API routes for dashboard statistics in the sign glove system.

Endpoints:
- GET /dashboard/: Legacy summary statistics for sessions, models, accuracy, and last activity.
- GET /dashboard/monitoring: Monitoring-first dashboard metrics.
"""
from datetime import datetime, timedelta, timezone
import logging
import math
import time
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException, Query
from pymongo import DESCENDING

from core.database import model_collection, sensor_collection
from core.error_handler import performance_monitor
from core.settings import settings

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

# Simple in-memory cache for dashboard stats
_dashboard_cache = {"data": None, "timestamp": 0}
_monitoring_cache: Dict[str, Dict[str, Any]] = {}
CACHE_TTL = 30  # seconds
MONITORING_CACHE_TTL = settings.MONITORING_CACHE_TTL_SECONDS
WINDOW_5M_SECONDS = settings.MONITORING_WINDOW_SECONDS
RUNTIME_HTTP_TIMEOUT_SECONDS = settings.MONITORING_RUNTIME_HEALTH_TIMEOUT_SECONDS

SENSOR_FIELDS_PROJECTION = {
    "timestamp": 1,
    "timestamp_ms": 1,
    "sensor_values": 1,
    "values": 1,
    "device_info": 1,
    "source": 1,
}


def _safe_round(value: float, digits: int = 4) -> float:
    if value is None:
        return 0.0
    return round(float(value), digits)


def _parse_timestamp(value: Any) -> Optional[datetime]:
    """Best-effort parser for mixed timestamp storage formats."""
    if value is None:
        return None

    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    if isinstance(value, (int, float)):
        num = float(value)
        # Heuristic: treat values >1e12 as milliseconds.
        if num > 1e12:
            num /= 1000.0
        try:
            return datetime.fromtimestamp(num, tz=timezone.utc)
        except Exception:
            return None

    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        # Numeric string fallback
        if raw.isdigit():
            return _parse_timestamp(int(raw))

        # Handle trailing Z
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"

        try:
            dt = datetime.fromisoformat(raw)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except Exception:
            return None

    return None


def _extract_timestamp(doc: Dict[str, Any]) -> Optional[datetime]:
    return _parse_timestamp(doc.get("timestamp")) or _parse_timestamp(doc.get("timestamp_ms"))


def _extract_sample_values(doc: Dict[str, Any]) -> List[List[float]]:
    """
    Returns normalized sample rows if available:
    - sensor_values: expected List[List[float]]
    - values: expected List[float] for single sample fallback
    """
    sensor_values = doc.get("sensor_values")
    if isinstance(sensor_values, list) and sensor_values and isinstance(sensor_values[0], list):
        return [row for row in sensor_values if isinstance(row, list)]

    values = doc.get("values")
    if isinstance(values, list) and values:
        if isinstance(values[0], list):
            return [row for row in values if isinstance(row, list)]
        return [values]

    return []


def _calc_percentile(values: List[float], percentile: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return float(values[0])

    sorted_values = sorted(values)
    k = (len(sorted_values) - 1) * percentile
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(sorted_values[int(k)])
    d0 = sorted_values[f] * (c - k)
    d1 = sorted_values[c] * (k - f)
    return float(d0 + d1)


def _parse_window_to_timedelta(window: str) -> timedelta:
    value = str(window or "").strip().lower()
    if value == "1h":
        return timedelta(hours=1)
    if value == "6h":
        return timedelta(hours=6)
    if value == "24h":
        return timedelta(hours=24)
    if value == "7d":
        return timedelta(days=7)
    raise HTTPException(status_code=400, detail="Invalid window. Allowed: 1h, 6h, 24h, 7d")


async def _probe_health_endpoint(name: str, base_url: str) -> Dict[str, Any]:
    url = f"{str(base_url).rstrip('/')}/health"
    try:
        async with httpx.AsyncClient(timeout=RUNTIME_HTTP_TIMEOUT_SECONDS) as client:
            response = await client.get(url)
    except Exception as exc:
        return {"name": name, "ok": False, "url": url, "error": str(exc)}

    payload = {}
    try:
        parsed = response.json()
        if isinstance(parsed, dict):
            payload = parsed
    except Exception:
        payload = {}

    return {
        "name": name,
        "ok": response.status_code < 400,
        "url": url,
        "status_code": int(response.status_code),
        "payload": payload,
    }


@router.get("/")
async def get_dashboard_stats():
    now = time.time()
    if _dashboard_cache["data"] is not None and now - _dashboard_cache["timestamp"] < CACHE_TTL:
        return _dashboard_cache["data"]
    try:
        # Count total gesture sessions
        try:
            total_sessions = await sensor_collection.count_documents({})
        except Exception as exc:
            logging.warning("Error counting sensor documents: %s", exc)
            total_sessions = 0

        # Count total training results
        try:
            total_models = await model_collection.count_documents({})
        except Exception as exc:
            logging.warning("Error counting model documents: %s", exc)
            total_models = 0

        # Average accuracy - handle empty collections
        acc_list = []
        try:
            cursor = model_collection.find({}, {"accuracy": 1})
            async for doc in cursor:
                if "accuracy" in doc and doc["accuracy"] is not None:
                    acc_list.append(doc["accuracy"])
        except Exception as exc:
            logging.warning("Error getting accuracy data: %s", exc)
            acc_list = []

        avg_accuracy = _safe_round(sum(acc_list) / len(acc_list), 4) if acc_list else 0.0

        # Latest timestamp from either collection
        latest_time = ""
        try:
            latest_sensor = await sensor_collection.find_one(sort=[("timestamp", DESCENDING)])
            latest_model = await model_collection.find_one(sort=[("timestamp", DESCENDING)])

            sensor_time = latest_sensor.get("timestamp", "") if latest_sensor else ""
            model_time = latest_model.get("timestamp", "") if latest_model else ""

            if sensor_time and model_time:
                latest_time = max(sensor_time, model_time)
            elif sensor_time:
                latest_time = sensor_time
            elif model_time:
                latest_time = model_time
        except Exception as exc:
            logging.warning("Error getting latest timestamps: %s", exc)
            latest_time = ""

        result = {
            "status": "success",
            "data": {
                "total_sessions": total_sessions,
                "total_models": total_models,
                "average_accuracy": avg_accuracy,
                "last_activity": latest_time,
            },
        }
        _dashboard_cache["data"] = result
        _dashboard_cache["timestamp"] = now
        return result
    except Exception as exc:
        logging.error("Dashboard stats error: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to get dashboard stats")


@router.get("/monitoring")
async def get_monitoring_dashboard_stats(
    window: str = Query("24h", pattern="^(1h|6h|24h|7d)$"),
):
    now = time.time()
    cache_key = f"window:{window}"
    cached = _monitoring_cache.get(cache_key)
    if cached and now - float(cached.get("timestamp", 0)) < MONITORING_CACHE_TTL:
        return cached["data"]

    try:
        now_dt = datetime.now(timezone.utc)
        recent_window = now_dt - _parse_window_to_timedelta(window)
        short_window = now_dt - timedelta(minutes=5)

        window_stats = performance_monitor.get_window_stats(
            window_seconds=WINDOW_5M_SECONDS,
            exclude_paths={"/dashboard/monitoring"},
        )
        recent_durations_ms = window_stats.get("durations_ms", [])
        total_requests = int(window_stats.get("request_count", 0))
        total_errors = int(window_stats.get("error_count", 0))

        latency_p95_ms = _safe_round(_calc_percentile(recent_durations_ms, 0.95), 2)
        error_rate_5m = _safe_round(float(window_stats.get("error_rate_pct", 0.0)), 4)
        throughput_rpm = _safe_round(total_requests / 5.0, 2) if total_requests else 0.0

        status = "healthy"
        if (
            error_rate_5m > settings.MONITORING_WARN_ERROR_RATE_5M_PCT
            or latency_p95_ms > settings.MONITORING_WARN_LATENCY_P95_MS
        ):
            status = "warning"
        if (
            error_rate_5m > settings.MONITORING_CRIT_ERROR_RATE_5M_PCT
            or latency_p95_ms > settings.MONITORING_CRIT_LATENCY_P95_MS
        ):
            status = "critical"

        # Pull recent sensor docs for traffic/data quality metrics.
        sensor_docs: List[Dict[str, Any]] = []
        sensor_cursor = sensor_collection.find(
            {},
            SENSOR_FIELDS_PROJECTION,
        ).sort("timestamp", DESCENDING).limit(1500)
        async for doc in sensor_cursor:
            ts = _extract_timestamp(doc)
            if ts is not None and ts >= recent_window:
                sensor_docs.append(doc)

        sensor_5m_docs = [doc for doc in sensor_docs if (_extract_timestamp(doc) or now_dt) >= short_window]
        sensor_24h_count = len(sensor_docs)
        sensor_5m_count = len(sensor_5m_docs)
        traffic_delta_pct = 0.0
        if sensor_24h_count:
            baseline_per_5m = sensor_24h_count / (24 * 12)
            if baseline_per_5m > 0:
                traffic_delta_pct = _safe_round(((sensor_5m_count - baseline_per_5m) / baseline_per_5m) * 100.0, 2)

        # Data quality heuristics.
        schema_mismatch_count = 0
        missing_value_count = 0
        total_value_slots = 0
        source_counts: Dict[str, int] = {}

        for doc in sensor_docs:
            samples = _extract_sample_values(doc)
            source = (
                doc.get("device_info", {}).get("source")
                if isinstance(doc.get("device_info"), dict)
                else doc.get("source", "unknown")
            ) or "unknown"
            source_counts[source] = source_counts.get(source, 0) + 1

            if not samples:
                schema_mismatch_count += 1
                continue

            for row in samples:
                if len(row) != 11:
                    schema_mismatch_count += 1
                total_value_slots += len(row)
                missing_value_count += sum(1 for value in row if value is None)

        missing_ratio = _safe_round((missing_value_count / total_value_slots) if total_value_slots else 0.0, 4)
        drop_rate = _safe_round((schema_mismatch_count / max(1, sensor_24h_count)), 4)

        # Model/performance snapshots.
        latest_model = await model_collection.find_one(sort=[("timestamp", DESCENDING)])
        previous_model = await model_collection.find_one(sort=[("timestamp", DESCENDING)], skip=1)

        active_version = "unavailable"
        previous_version = "n/a"
        rollout_percent = 100
        last_deploy_at = None
        model_accuracy = None

        if latest_model:
            active_version = (
                latest_model.get("model_version")
                or latest_model.get("version")
                or latest_model.get("model_name")
                or str(latest_model.get("_id"))
            )
            last_deploy = _extract_timestamp(latest_model)
            last_deploy_at = last_deploy.isoformat() if last_deploy else None
            raw_acc = latest_model.get("accuracy")
            if isinstance(raw_acc, (int, float)):
                model_accuracy = _safe_round(float(raw_acc), 4)

        if previous_model:
            previous_version = (
                previous_model.get("model_version")
                or previous_model.get("version")
                or previous_model.get("model_name")
                or str(previous_model.get("_id"))
            )

        # Drift heuristics based on source concentration change.
        top_sources = sorted(source_counts.items(), key=lambda item: item[1], reverse=True)
        dominant_ratio = (top_sources[0][1] / sensor_24h_count) if sensor_24h_count and top_sources else 0.0
        global_drift_score = _safe_round(min(1.0, dominant_ratio), 4)

        top_shifted_features = []
        for source, count in top_sources[:3]:
            share = _safe_round((count / sensor_24h_count) * 100.0, 2) if sensor_24h_count else 0.0
            top_shifted_features.append({"feature": f"source:{source}", "shift": share})

        runtime_checks: List[Dict[str, Any]] = []
        if settings.USE_RUNTIME_SERVICES:
            runtime_checks.extend([
                await _probe_health_endpoint("ml-tensorflow", settings.ML_TENSORFLOW_URL),
                await _probe_health_endpoint("ml-pytorch", settings.ML_PYTORCH_URL),
            ])
        if settings.USE_WORKER_LIBRARY:
            runtime_checks.append(await _probe_health_endpoint("worker-library", settings.WORKER_LIBRARY_URL))

        # Events feed.
        latest_sensor_ts = None
        for doc in sensor_docs:
            ts = _extract_timestamp(doc)
            if ts is not None:
                latest_sensor_ts = ts
                break

        alerts: List[Dict[str, Any]] = []
        if status == "critical":
            alerts.append(
                {
                    "id": "health-critical",
                    "severity": "critical",
                    "title": "Service health degraded",
                    "message": f"p95={latency_p95_ms}ms, error_rate_5m={error_rate_5m}%",
                    "timestamp": now_dt.isoformat(),
                }
            )
        elif status == "warning":
            alerts.append(
                {
                    "id": "health-warning",
                    "severity": "warning",
                    "title": "Service health warning",
                    "message": f"p95={latency_p95_ms}ms, error_rate_5m={error_rate_5m}%",
                    "timestamp": now_dt.isoformat(),
                }
            )

        runtime_failures = [check for check in runtime_checks if not check.get("ok")]
        for failure in runtime_failures:
            alerts.append(
                {
                    "id": f"runtime-{failure.get('name')}",
                    "severity": "critical",
                    "title": f"{failure.get('name')} unavailable",
                    "message": failure.get("error") or f"HTTP {failure.get('status_code', 'unknown')}",
                    "timestamp": now_dt.isoformat(),
                }
            )
        if runtime_failures:
            status = "critical"

        if (
            drop_rate >= settings.MONITORING_WARN_DROP_RATE
            or missing_ratio >= settings.MONITORING_WARN_MISSING_RATIO
        ):
            alerts.append(
                {
                    "id": "data-quality-warning",
                    "severity": "warning",
                    "title": "Data quality anomaly",
                    "message": f"drop_rate={_safe_round(drop_rate * 100, 2)}%, missing_ratio={_safe_round(missing_ratio * 100, 2)}%",
                    "timestamp": now_dt.isoformat(),
                }
            )
            if status == "healthy":
                status = "warning"

        if global_drift_score >= settings.MONITORING_WARN_DRIFT_SCORE:
            alerts.append(
                {
                    "id": "drift-elevated",
                    "severity": "warning",
                    "title": "Drift score elevated",
                    "message": f"global_drift_score={global_drift_score}",
                    "timestamp": now_dt.isoformat(),
                }
            )
            if status == "healthy":
                status = "warning"

        if not alerts:
            alerts.append(
                {
                    "id": "health-ok",
                    "severity": "info",
                    "title": "System healthy",
                    "message": "No active monitoring alerts",
                    "timestamp": now_dt.isoformat(),
                }
            )

        critical_alert_count = sum(1 for alert in alerts if alert.get("severity") == "critical")
        warning_alert_count = sum(1 for alert in alerts if alert.get("severity") == "warning")

        events = [
            {
                "type": "health_status",
                "severity": "critical" if status == "critical" else "info",
                "message": f"System status is {status}",
                "timestamp": now_dt.isoformat(),
            },
            {
                "type": "traffic_snapshot",
                "severity": "info",
                "message": f"Captured {sensor_5m_count} sensor documents in the last 5 minutes",
                "timestamp": now_dt.isoformat(),
            },
        ]
        if last_deploy_at:
            events.append(
                {
                    "type": "model_deploy",
                    "severity": "info",
                    "message": f"Active model version: {active_version}",
                    "timestamp": last_deploy_at,
                }
            )
        if latest_sensor_ts:
            events.append(
                {
                    "type": "data_ingest",
                    "severity": "info",
                    "message": "Latest sensor ingest received",
                    "timestamp": latest_sensor_ts.isoformat(),
                }
            )
        for check in runtime_checks:
            events.append(
                {
                    "type": "runtime_service",
                    "severity": "warning" if not check.get("ok") else "info",
                    "message": f"{check.get('name')}: {'healthy' if check.get('ok') else 'unreachable'}",
                    "timestamp": now_dt.isoformat(),
                }
            )

        # Performance trend from latest model accuracy history (best effort).
        trend_points: List[Dict[str, Any]] = []
        perf_cursor = model_collection.find(
            {"timestamp": {"$gte": recent_window}},
            {"timestamp": 1, "accuracy": 1},
        ).sort("timestamp", 1).limit(96)
        async for model_doc in perf_cursor:
            ts = _extract_timestamp(model_doc)
            acc = model_doc.get("accuracy")
            if ts is not None and isinstance(acc, (int, float)):
                trend_points.append({"timestamp": ts.isoformat(), "value": _safe_round(float(acc), 4)})

        segment_regressions = []
        if top_sources:
            for source, count in top_sources[:3]:
                segment_regressions.append(
                    {
                        "segment": source,
                        "impact": _safe_round((count / max(1, sensor_24h_count)) * 100.0, 2),
                    }
                )

        monitoring = {
            "status": "success",
            "data": {
                "health": {
                    "status": status,
                    "uptime_24h": 99.9,
                    "error_rate_5m": error_rate_5m,
                    "latency_p95_ms": latency_p95_ms,
                    "throughput_rpm": throughput_rpm,
                },
                "alerts": {
                    "open_total": critical_alert_count + warning_alert_count,
                    "critical": critical_alert_count,
                    "warning": warning_alert_count,
                    "latest": alerts,
                },
                "model": {
                    "active_version": active_version,
                    "previous_version": previous_version,
                    "rollout_percent": rollout_percent,
                    "last_deploy_at": last_deploy_at,
                },
                "runtime_services": runtime_checks,
                "traffic": {
                    "requests_last_5m": sensor_5m_count,
                    "requests_last_24h": sensor_24h_count,
                    "trend_delta_pct": traffic_delta_pct,
                },
                "data_quality": {
                    "missing_ratio": missing_ratio,
                    "schema_mismatch_count": schema_mismatch_count,
                    "drop_rate": drop_rate,
                },
                "drift": {
                    "global_score": global_drift_score,
                    "top_shifted_features": top_shifted_features,
                },
                "performance": {
                    "metric_name": "accuracy",
                    "window": window,
                    "current_value": model_accuracy if model_accuracy is not None else 0.0,
                    "trend": trend_points,
                    "segment_regressions": segment_regressions,
                },
                "events": sorted(events, key=lambda item: item["timestamp"], reverse=True),
                "meta": {
                    "window": window,
                    "generated_at": now_dt.isoformat(),
                    "thresholds": {
                        "warn_error_rate_5m_pct": settings.MONITORING_WARN_ERROR_RATE_5M_PCT,
                        "crit_error_rate_5m_pct": settings.MONITORING_CRIT_ERROR_RATE_5M_PCT,
                        "warn_latency_p95_ms": settings.MONITORING_WARN_LATENCY_P95_MS,
                        "crit_latency_p95_ms": settings.MONITORING_CRIT_LATENCY_P95_MS,
                        "warn_drop_rate": settings.MONITORING_WARN_DROP_RATE,
                        "warn_missing_ratio": settings.MONITORING_WARN_MISSING_RATIO,
                        "warn_drift_score": settings.MONITORING_WARN_DRIFT_SCORE,
                    },
                },
            },
        }

        _monitoring_cache[cache_key] = {"data": monitoring, "timestamp": now}
        return monitoring
    except Exception as exc:
        logging.error("Monitoring dashboard stats error: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to get monitoring dashboard stats")


@router.get("")
async def get_dashboard_stats_alias():
    return await get_dashboard_stats()
