# SignGlove V3 Migration Plan — Tasks 9–11 (Status: In Progress)

## Overview

After completing **Tasks 1–8**, the SignGlove backend has a modular structure, async workers, and basic artifact storage. The project is currently transitioning through **Tasks 9–11**, with infrastructure for observability and job tracking partially in place.

---

# Task 9 — Observability & System Monitoring (Status: 60% Complete)

## Progress
*   **Infrastructure:** Prometheus and Grafana containers are defined in `docker-compose.yml`.
*   **API Instrumentation:** `prometheus-fastapi-instrumentator` is integrated into `api/main.py`.
*   **Configuration:** `monitoring/prometheus.yml` is configured to scrape API and Worker services.

## Remaining Work
*   **ML Service Metrics:** Instrument `ml-tensorflow` and `ml-pytorch` to expose inference latency and throughput.
*   **Worker Metrics:** Implement a Celery metrics exporter to track queue depth and task success rates.
*   **Dashboards:** Provision Grafana dashboards for "API Health," "Inference Performance," and "Worker Throughput."

---

# Task 10 — Job Status & Progress Tracking (Status: 40% Complete)

## Progress
*   **Async Engine:** Celery/Redis backend is operational.
*   **Task Updates:** Workers update state via `self.update_state(state="PROGRESS", ...)` and persistent sidecar metadata files.
*   **Service Integration:** `admin_csv_library_routes.py` includes job status endpoints.

## Remaining Work
*   **Persistent Jobs Table:** Create the `jobs` table in Postgres (via Alembic) for long-term audit logs (Status: Missing).
*   **Centralized API:** Implement a global `/jobs` router to track all async tasks (Scans, Preprocessing, Training) in one place.
*   **Standardized States:** Formalize `pending -> running -> completed/failed` transitions across all worker types.

---

# Task 11 — API Gateway Hardening (Status: 50% Complete)

## Progress
*   **Authentication:** JWT-based authentication is implemented in `auth_routes.py`.
*   **Validation:** Strict Pydantic schemas are enforced for most endpoints.
*   **Middleware:** Basic security headers and in-memory rate limiting are active.

## Remaining Work
*   **Redis Rate Limiting:** Replace the current in-memory `RateLimitMiddleware` with a persistent Redis-backed solution (e.g., `slowapi`).
*   **Strict Upload Limits:** Enforce the 500MB (CSV) and 2GB (Model) limits in `model_library_routes.py`. Currently, models are read entirely into memory.
*   **Timeout & Circuit Breaking:** Configure explicit timeouts for `httpx` calls between the API and ML runtimes to prevent cascading failures.

---

# Result After Task 11 (Projected)

After completing the remaining hardening, the SignGlove backend will be a **production-ready ML platform**.

Final architecture:
```
Client -> [Auth/Rate Limit] -> API Gateway -> [Service Layer] -> [Celery Queue] -> Workers
                                     │                                         │
                                     └───────────> [Prometheus/Grafana] <──────┘
```

---

# Future Extensions (Updated)

### Task 12 — Production Hardening (Cleanup)
Finalize missing Task 11 items:
*   Move Rate Limiting to Redis.
*   Implement `StreamingResponse` for model uploads to prevent OOM errors.
*   Centralize `httpx` client timeouts.

### Task 13 — Centralized Job Management
*   Migrate job tracking from sidecar files to the Postgres `jobs` table.
*   Expose `/api/v1/jobs` with filtering by `task_type` and `user_id`.

### Task 14 — Experiment Tracking & Versioning
Track ML experiments including:
*   Dataset versions (Lineage).
*   Hyperparameters and validation metrics.
*   Model artifact hash verification.

### Task 15 — GPU Worker Pool
Introduce specialized workers:
*   `cpu-workers` (Preprocessing, Scans).
*   `gpu-workers` (Training, Real-time video inference).

---

# Summary

The SignGlove V3 architecture evolves from a **monolithic ML web app** into a **scalable ML experimentation platform** focused on:

* dataset lifecycle
* model management
* inference experimentation
* asynchronous ML workflows
* system observability
 