# SignGlove V3 Migration Plan — Tasks 9–11

## Overview

After completing **Tasks 1–8**, the SignGlove backend has:

* Modular project structure
* Service layer separation
* Async workers
* Dataset processing offloaded from API
* Model artifact storage
* Database migrations

The next phase focuses on **production readiness**, introducing:

* Observability
* Job tracking
* API hardening

---

# Task 9 — Observability & System Monitoring

## Scope

Introduce system observability for **API, workers, and ML runtime services**.

The platform must expose metrics to monitor:

* API latency
* Worker queue size
* Job processing time
* Failed tasks
* ML inference duration

## Architecture

```
API / Workers
     │
     ▼
Prometheus → Metrics collection
     │
     ▼
Grafana → Visualization dashboards
```

## Implementation

### API Metrics

Add instrumentation:

```
prometheus-fastapi-instrumentator
```

Track:

```
request_latency_seconds
request_count
error_rate
```

Expose endpoint:

```
GET /metrics
```

### Worker Metrics

Expose metrics such as:

```
jobs_processed_total
jobs_failed_total
job_duration_seconds
queue_depth
```

### Queue Monitoring

Monitor Redis queue state:

```
pending_jobs
active_workers
worker_health
```

## Constraints

* Monitoring must remain lightweight
* Metrics must not degrade API performance

## Tests

Verify Prometheus can scrape metrics:

```
GET /metrics
```

Confirm metrics appear in Grafana dashboard.

## Acceptance Criteria

* Grafana dashboards operational
* API metrics visible
* Worker metrics visible
* Queue depth visible

---

# Task 10 — Job Status & Progress Tracking

## Scope

Introduce a **job tracking system** for asynchronous tasks.

Users must be able to view:

* job status
* job progress
* errors
* result location

## Database Table

Create table:

```
jobs
```

Example schema:

```
id
task_type
status
progress
created_at
started_at
finished_at
error_message
result_location
```

### Job Status States

```
pending
running
completed
failed
```

## API Endpoints

Submit job:

```
POST /jobs
```

Check job status:

```
GET /jobs/{job_id}
```

List jobs:

```
GET /jobs
```

## Worker Behavior

Workers must update job lifecycle:

```
pending → running → completed
```

or

```
pending → running → failed
```

Workers should also update progress percentage.

Example:

```
progress = 45%
```

## Tests

Upload dataset:

```
POST /datasets/upload
```

API returns:

```
job_id
```

Then verify status:

```
GET /jobs/{job_id}
```

## Acceptance Criteria

* Jobs table exists
* Worker updates job status
* API exposes job status endpoint
* Users can track async tasks

---

# Task 11 — API Gateway Hardening

## Scope

Prepare API for production exposure.

Add safeguards including:

* authentication
* rate limiting
* strict request validation
* timeout handling
* file upload limits

## Authentication

Use JWT authentication.

Example flow:

```
POST /auth/login
→ returns JWT token
```

Protected endpoints require:

```
Authorization: Bearer <token>
```

Optional extension:

```
OAuth2 login
```

## Rate Limiting

Introduce Redis-based rate limiting.

Example policy:

```
100 requests per minute per user
```

Possible implementation:

```
slowapi
redis
```

## Request Validation

Strict Pydantic schemas for:

```
datasets
models
inference requests
```

Reject malformed requests early.

## Timeout Handling

Prevent API blocking when services stall.

Example configuration:

```
httpx timeout = 5 seconds
```

## File Upload Security

Limit file sizes:

```
CSV dataset max = 500MB
Model artifact max = 2GB
```

Validate file extensions:

```
.csv
.json
.pt
.h5
```

Prevent:

```
path traversal
malicious payloads
```

## Tests

Simulate:

```
invalid tokens
request spam
oversized uploads
```

Verify system stability.

## Acceptance Criteria

* JWT authentication implemented
* Rate limiting enforced
* File upload limits active
* API resilient to misuse

---

# Result After Task 11

After completing Tasks 9–11, the SignGlove backend becomes a **production-ready ML platform backend**.

Final architecture:

```
Client
   │
   ▼
API Gateway
   │
   ▼
Service Layer
   │
   ▼
Worker Queue
   │
   ▼
Workers
```

Platform capabilities:

* Dataset management
* Model registry
* Asynchronous ML workflows
* Observability and monitoring
* Job tracking
* Secure API gateway

---

# Future Extensions

Recommended next tasks:

### Task 12 — Experiment Tracking

Track ML experiments including:

```
dataset
model version
metrics
hyperparameters
```

### Task 13 — Dataset Versioning

Add dataset lineage support:

```
dataset_versions
dataset_history
```

### Task 14 — GPU Worker Pool

Introduce specialized workers:

```
cpu-workers
gpu-workers
```

GPU tasks include:

```
training
large-scale inference
video processing
```

---

# Summary

The SignGlove V3 architecture evolves from a **monolithic ML web app** into a **scalable ML experimentation platform** focused on:

* dataset lifecycle
* model management
* inference experimentation
* asynchronous ML workflows
* system observability
 88888888888888