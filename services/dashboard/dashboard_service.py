import logging
import math
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx
from pymongo import DESCENDING

from api.core.database import model_collection, sensor_collection
from api.core.error_handler import performance_monitor
from api.core.settings import settings

logger = logging.getLogger("signglove.dashboard_service")

# Constants from router
CACHE_TTL = 30
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

# --- Helpers ---

def _safe_round(value: float, digits: int = 4) -> float:
    if value is None: return 0.0
    try: return round(float(value), digits)
    except: return 0.0

def _parse_timestamp(value: Any) -> Optional[datetime]:
    if value is None: return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        num = float(value)
        if num > 1e12: num /= 1000.0
        try: return datetime.fromtimestamp(num, tz=timezone.utc)
        except: return None
    if isinstance(value, str):
        raw = value.strip()
        if not raw: return None
        if raw.isdigit(): return _parse_timestamp(int(raw))
        if raw.endswith("Z"): raw = raw[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(raw)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except: return None
    return None

def _extract_timestamp(doc: Dict[str, Any]) -> Optional[datetime]:
    return _parse_timestamp(doc.get("timestamp")) or _parse_timestamp(doc.get("timestamp_ms"))

def _extract_sample_values(doc: Dict[str, Any]) -> List[List[float]]:
    sv = doc.get("sensor_values")
    if isinstance(sv, list) and sv and isinstance(sv[0], list):
        return [row for row in sv if isinstance(row, list)]
    v = doc.get("values")
    if isinstance(v, list) and v:
        if isinstance(v[0], list): return [row for row in v if isinstance(row, list)]
        return [v]
    return []

def _calc_percentile(values: List[float], percentile: float) -> float:
    if not values: return 0.0
    if len(values) == 1: return float(values[0])
    sorted_values = sorted(values)
    k = (len(sorted_values) - 1) * percentile
    f = math.floor(k)
    c = math.ceil(k)
    if f == c: return float(sorted_values[int(k)])
    return float(sorted_values[f] * (c - k) + sorted_values[c] * (k - f))

async def _probe_health_endpoint(name: str, base_url: str) -> Dict[str, Any]:
    url = f"{str(base_url).rstrip('/')}/health"
    try:
        async with httpx.AsyncClient(timeout=RUNTIME_HTTP_TIMEOUT_SECONDS) as client:
            resp = await client.get(url)
            payload = {}
            try: payload = resp.json()
            except: pass
            return {
                "name": name,
                "ok": resp.status_code < 400,
                "url": url,
                "status_code": int(resp.status_code),
                "payload": payload if isinstance(payload, dict) else {},
            }
    except Exception as exc:
        return {"name": name, "ok": False, "url": url, "error": str(exc)}

class DashboardService:
    def __init__(self):
        self._dashboard_cache = {"data": None, "timestamp": 0}
        self._monitoring_cache: Dict[str, Dict[str, Any]] = {}

    async def get_basic_stats(self) -> Dict[str, Any]:
        now = time.time()
        if self._dashboard_cache["data"] and now - self._dashboard_cache["timestamp"] < CACHE_TTL:
            return self._dashboard_cache["data"]

        total_sessions = await sensor_collection.count_documents({})
        total_models = await model_collection.count_documents({})
        
        acc_list = []
        async for doc in model_collection.find({}, {"accuracy": 1}):
            if doc.get("accuracy") is not None:
                acc_list.append(doc["accuracy"])
        
        avg_acc = _safe_round(sum(acc_list)/len(acc_list)) if acc_list else 0.0
        
        latest_sensor = await sensor_collection.find_one(sort=[("timestamp", DESCENDING)])
        latest_model = await model_collection.find_one(sort=[("timestamp", DESCENDING)])
        
        s_time = latest_sensor.get("timestamp", "") if latest_sensor else ""
        m_time = latest_model.get("timestamp", "") if latest_model else ""
        latest_time = max(str(s_time), str(m_time)) if s_time and m_time else (s_time or m_time or "")

        result = {
            "status": "success",
            "data": {
                "total_sessions": total_sessions,
                "total_models": total_models,
                "average_accuracy": avg_acc,
                "last_activity": latest_time,
            }
        }
        self._dashboard_cache = {"data": result, "timestamp": now}
        return result

    async def get_monitoring_stats(self, window_str: str) -> Dict[str, Any]:
        now = time.time()
        cache_key = f"window:{window_str}"
        cached = self._monitoring_cache.get(cache_key)
        if cached and now - cached["timestamp"] < MONITORING_CACHE_TTL:
            return cached["data"]

        now_dt = datetime.now(timezone.utc)
        
        # Window parsing
        w_map = {"1h": 1, "6h": 6, "24h": 24, "7d": 168}
        hours = w_map.get(window_str, 24)
        recent_window = now_dt - timedelta(hours=hours)
        short_window = now_dt - timedelta(minutes=5)

        stats = performance_monitor.get_window_stats(WINDOW_5M_SECONDS, {"/dashboard/monitoring"})
        durations = stats.get("durations_ms", [])
        p95 = _safe_round(_calc_percentile(durations, 0.95), 2)
        error_rate = _safe_round(float(stats.get("error_rate_pct", 0.0)), 4)
        
        # Sensor data analysis
        sensor_docs = []
        async for doc in sensor_collection.find({}, SENSOR_FIELDS_PROJECTION).sort("timestamp", DESCENDING).limit(1500):
            ts = _extract_timestamp(doc)
            if ts and ts >= recent_window: sensor_docs.append(doc)
        
        sensor_5m = [d for d in sensor_docs if (_extract_timestamp(d) or now_dt) >= short_window]
        
        # Runtime checks
        runtime_checks = []
        if settings.USE_RUNTIME_SERVICES:
            runtime_checks.append(await _probe_health_endpoint("ml-tensorflow", settings.ML_TENSORFLOW_URL))
            runtime_checks.append(await _probe_health_endpoint("ml-pytorch", settings.ML_PYTORCH_URL))
        if settings.USE_WORKER_LIBRARY:
            runtime_checks.append(await _probe_health_endpoint("worker-library", settings.WORKER_LIBRARY_URL))

        # Basic alert logic
        status = "healthy"
        if error_rate > settings.MONITORING_WARN_ERROR_RATE_5M_PCT or p95 > settings.MONITORING_WARN_LATENCY_P95_MS:
            status = "warning"
        if error_rate > settings.MONITORING_CRIT_ERROR_RATE_5M_PCT or p95 > settings.MONITORING_CRIT_LATENCY_P95_MS:
            status = "critical"
        if any(not c["ok"] for c in runtime_checks): status = "critical"

        monitoring = {
            "status": "success",
            "data": {
                "health": {"status": status, "error_rate_5m": error_rate, "latency_p95_ms": p95},
                "runtime_services": runtime_checks,
                "traffic": {"requests_last_5m": len(sensor_5m), "requests_last_24h": len(sensor_docs)},
                "meta": {"window": window_str, "generated_at": now_dt.isoformat()}
            }
        }
        self._monitoring_cache[cache_key] = {"data": monitoring, "timestamp": now}
        return monitoring

dashboard_service = DashboardService()
