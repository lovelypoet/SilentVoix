# SignGlove V3 Migration Plan — Tasks 9–11 (Status: Finalizing)

## Overview

SignGlove V3 has successfully transitioned from a monolithic architecture to a production-ready ML platform. Core components for async job tracking and API hardening are now fully integrated.

---

# Task 9 — Observability & System Monitoring (Status: 60% Complete)

## Progress
*   **Infrastructure:** Prometheus and Grafana containers are active in `docker-compose.yml`.
*   **API Instrumentation:** Full request/response metrics are exposed via `/metrics`.
*   **Configuration:** `monitoring/prometheus.yml` is configured for API and Worker scraping.

## Remaining Work
*   **Worker/ML Metrics:** Expose inference latency (YOLO/Transformer) and queue depth directly.
*   **Dashboards:** Provision Grafana dashboards for performance monitoring and error rates.

---

# Task 10 — Job Status & Progress Tracking (Status: 100% Complete)

## Progress
*   **Persistent Jobs Table:** `JobRecord` table created in Postgres (via Alembic) for permanent audit logs.
*   **Centralized API:** Global `/jobs` and `/jobs/{id}` endpoints implemented in `job_routes.py`.
*   **Lifecycle Integration:** Dataset scan tasks update `JobRecord` states (`pending -> running -> completed/failed`) with progress increments.
*   **Security:** Job visibility is restricted to the owner (`user_id`) or administrators.
*   **Verification:** Verified via automated smoke test (Persistent state + polling success).

---

# Task 11 — API Gateway Hardening (Status: 100% Complete)

## Progress
*   **Redis Rate Limiting:** Persistent Redis-backed (DB 1) rate limiting implemented.
*   **Strict Upload Security:** 500MB (CSV) and 2GB (Model) limits enforced at the stream level.
*   **Resource Safety:** Disk-buffered streaming uploads implemented in `upload_utils.py` to prevent OOM errors.
*   **Authentication:** JWT-based role enforcement (Admin/Editor/Guest) is active across all V3 routes.
*   **Verification:** Verified via stress test (Correctly triggers 429 after limit exceeded; streaming move success).

---

# Current Architecture (Implemented)

```
Client ──> [JWT Auth / Redis Rate Limit] ──> API Gateway ──> [Service Layer] ──> [Celery Queue] ──> Workers
                                                  │                                          │
                                                  └─────────> [Postgres JobRecord] <─────────┘
                                                  │                                          │
                                            [Prometheus] <──────── [Disk-Buffered Uploads] <─┘
```

---

# Future Roadmap (Updated)

### Task 12 — Observability & Analytics (Cleanup)
*   **Grafana Dashboards:** Provision standard dashboards for system health.
*   **ML Metrics:** Expose confidence score histograms and pipeline latency to Prometheus.
*   **Circuit Breaking:** Implement retry logic and timeouts for service-to-service communication.

### Task 13 — Experiment Tracking & Versioning
*   **Dataset Versioning:** Track lineage between models and specific dataset hashes.
*   **Hyperparameter Logging:** Save training config alongside the `Model` record.
*   **Artifact Integrity:** Add SHA-256 verification for uploaded models.

### Task 14 — specialized GPU Worker Pools
*   Configure specialized queues for GPU-intensive tasks (Training, YOLO Video Inference).
