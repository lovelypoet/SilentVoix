# SignGlove V3 – Architecture Risks & Best Practices Review

This document summarizes critical architectural pitfalls that commonly break ML platforms at scale and the recommended patterns implemented in SignGlove V3 to avoid them.

---

# 1. Artifact Chaos (Model Versioning)

## Problem
Without a strict artifact versioning strategy, model storage quickly becomes disorganized (`final.pt`, `best_new.pt`, etc.), making it impossible to determine which model version is active or reproducible.

## Mitigation: Immutable Model Versioning (Implemented)
Use a structured, immutable layout where each version is isolated:
```
storage/models/{model_name}/{version}/
   ├── model.pt
   └── metadata.json
```
*   **Status:** ✅ Implemented in `ModelService`.
*   **Rule:** Workers must **never overwrite** existing version folders.

---

# 2. Worker Explosion & Queue Starvation

## Problem
Moving every operation into a single generic worker creates queue starvation, unpredictable latency, and hard-to-debug memory leaks.

## Mitigation: Specialized Workers (Ongoing)
Isolate tasks into dedicated queues:
*   **Dataset Worker:** Handles CSV parsing, validation, and preprocessing.
*   **Inference Worker:** Handles batch inference and model evaluation.
*   **Metrics Worker:** Handles analytics and performance scoring.
*   **Status:** ⚠️ Partial. `dataset_scan` is isolated, but further specialization is planned.

---

# 3. API Orchestration Overload

## Problem
Turning the API into a central orchestration engine (calling multiple workers and waiting) creates a "distributed monolith" with high latency and cascading failures.

## Mitigation: Event-Driven Job Tracking (Implemented)
The API only enqueues jobs and returns a `job_id` immediately.
*   **Pattern:** API -> Redis -> Worker -> Postgres (`JobRecord`).
*   **Status:** ✅ Implemented. Global `/jobs` router and `JobRecord` table track async lifecycle.

---

# 4. Production Hardening (Security & Stability)

## Risk: Resource Exhaustion (OOM)
Uploading multi-gigabyte files directly into memory crashes the API.
*   **Mitigation:** **Streaming Disk-Buffered Uploads**. Files are processed in 1MB chunks and buffered to `/tmp/uploads` with strict enforcement of 500MB (CSV) and 2GB (Model) limits.
*   **Status:** ✅ Implemented in `upload_utils.py`.

## Risk: Request Flooding (DoS)
Malicious or buggy clients can overwhelm the system with rapid-fire requests.
*   **Mitigation:** **Redis-backed Rate Limiting**. Uses Redis (DB 1) to enforce a persistent 60 requests/minute policy per IP.
*   **Status:** ✅ Implemented in `RateLimitMiddleware`.

---

# 5. Model Loading Latency

## Problem
Loading a model from disk for every inference request causes multi-second latency.

## Mitigation: Warm-Loading (Implemented)
Load models once during service startup or on the first request, then cache them in the runtime memory.
*   **Status:** ✅ Implemented in `ml-tensorflow` and `ml-pytorch` services via `_MODEL_CACHE`.

---

# 6. Implementation Scorecard (March 2026)

| Risk Category | Status | Mitigation Strategy |
| :--- | :--- | :--- |
| **Artifact Chaos** | ✅ Resolved | Immutable directory structure per version. |
| **Worker Explosion** | ⚠️ Partial | Isolated `dataset_scan` tasks; more queues needed. |
| **Orchestration Overload** | ✅ Resolved | Async job tracking via `JobRecord` & Postgres. |
| **Model Loading Latency** | ✅ Resolved | In-memory caching in ML runtimes. |
| **Resource Exhaustion** | ✅ Resolved | Streaming uploads with hard 500MB/2GB limits. |
| **Security/DoS** | ✅ Resolved | JWT Authentication + Redis Rate Limiting (DB 1). |

---

# 7. Target Architecture

```
Frontend ──> [Auth/Rate Limit] ──> API Gateway ──> [Service Layer] ──> [Celery Queue] ──> Workers
                                        │                                          │
                                        └──────────> [Prometheus/Grafana] <────────┘
                                        │                                          │
                                  [Postgres DB] <─────── [Artifacts] <─────── [ML Runtimes]
```

---

# Summary

To maintain the stability of the SignGlove system:
1.  **Immutability:** Never overwrite model artifacts; version everything.
2.  **Asynchronicity:** API returns `job_id` immediately; work happens in the background.
3.  **Resource Control:** Enforce strict upload limits and rate limits at the gateway.
4.  **Specialization:** Keep workers focused on single domains to prevent queue starvation.
