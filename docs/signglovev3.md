# SignGlove Service Architecture Reform

## Purpose

This document defines the **service architecture** for the SignGlove platform after moving away from web-based training.
SignGlove now acts as a **developer-first ML playground** focused on:

* dataset management
* model registry
* inference playground
* experiment evaluation

Training is **not executed in the web backend**. Models are trained externally and uploaded to the platform.

---

# High-Level System Architecture

```
Client (Web UI / CLI)
        │
        ▼
     FastAPI API
        │
 ┌──────┼───────────────────────────┐
 │      │                           │
 ▼      ▼                           ▼
Dataset Service     Model Registry Service     Playground Service
 │                  │                         │
 │                  │                         ▼
 │                  │                 Worker Queue
 │                  │                         │
 │                  ▼                         ▼
 │           Model Storage            Async Workers
 │
 ▼
Dataset Storage
```

---

# Core Services

## 1. API Gateway

Location:

```
api/
```

Responsibilities:

* HTTP endpoints
* authentication
* request validation
* routing to services

Framework:

* FastAPI

Example responsibilities:

```
POST /datasets/upload
POST /models/upload
POST /playground/run
GET /models
GET /datasets
```

The API layer **must remain lightweight** and avoid heavy processing.

---

# 2. Dataset Service

Location:

```
services/datasets/
```

Responsibilities:

* CSV upload
* dataset metadata management
* dataset preview
* dataset versioning

Example operations:

```
upload_dataset()
list_datasets()
get_dataset_preview()
select_dataset()
```

Processing pipeline:

```
CSV upload
    │
    ▼
dataset parser worker
    │
    ▼
store metadata + data
```

Storage:

* metadata → SQL database
* raw dataset → object storage or database

---

# 3. Model Registry Service

Location:

```
services/models/
```

Responsibilities:

* model upload
* versioning
* model metadata
* model artifact management

Example operations:

```
register_model()
upload_model_artifact()
list_models()
get_model_version()
```

Model artifact formats:

```
.pth
.onnx
.pt
```

Artifact storage may use:

```
local filesystem
S3-compatible storage
```

Metadata stored in SQL.

---

# 4. Playground Service

Location:

```
services/playground/
```

Purpose:

Run inference experiments using uploaded models and datasets.

Example flow:

```
select model
select dataset
run inference
view metrics
```

Operations:

```
run_inference()
evaluate_predictions()
compare_models()
```

Heavy tasks must be sent to workers.

---

# 5. Worker Service

Location:

```
workers/
```

Purpose:

Execute asynchronous jobs that are too heavy for the API server.

Worker tasks:

```
dataset parsing
batch inference
metric computation
evaluation
```

Worker flow:

```
API request
    │
    ▼
queue job
    │
    ▼
worker executes task
    │
    ▼
store results
```

Workers should be stateless and horizontally scalable.

---

# 6. Storage Layer

Location:

```
storage/
```

Responsibilities:

```
model artifacts
dataset files
temporary processing data
```

Example structure:

```
storage/
   models/
      model_name/
         v1/
         v2/
   datasets/
      dataset_name/
         raw.csv
         processed.parquet
```

---

# 7. Database Layer

Location:

```
db/
```

Purpose:

Store system metadata.

Example entities:

```
users
datasets
models
model_versions
predictions
sessions
sensor_data
```

The database must **not store large model files or raw datasets**.

---

# 8. Monitoring Service

Location:

```
monitoring/
```

Purpose:

Track system performance.

Metrics:

```
API latency
worker job queue size
inference duration
dataset size
```

Dashboards allow developers to observe system health.

---

# Worker Task Types

Examples:

```
parse_dataset(csv_file)
run_inference(model_id, dataset_id)
compute_metrics(predictions)
generate_evaluation_report()
```

Workers must be idempotent and retry-safe.

---

# Folder Structure

Recommended repository layout:

```
signglove/

api/
    main.py
    routes/

services/
    datasets/
    models/
    playground/

workers/
    tasks/
    worker.py

storage/
    models/
    datasets/

db/
    models.py
    migrations/

monitoring/
    dashboards/

docker/
    docker-compose.yml
```

---

# Data Flow Examples

## Dataset Upload

```
Client
   │
   ▼
API upload endpoint
   │
   ▼
queue dataset parsing job
   │
   ▼
worker parses CSV
   │
   ▼
store dataset metadata
```

---

## Model Upload

```
Client
   │
   ▼
API model upload
   │
   ▼
store model artifact
   │
   ▼
register model version
```

---

## Playground Inference

```
Client selects model + dataset
       │
       ▼
API request
       │
       ▼
queue inference job
       │
       ▼
worker loads model
       │
       ▼
run predictions
       │
       ▼
store results
```

---

# Design Principles

1. API must remain lightweight.
2. Heavy work must run in workers.
3. Models are trained outside the platform.
4. Dataset processing must be asynchronous.
5. Services must remain modular.

---

# Future Extensions

Possible improvements:

```
experiment tracking
model comparison dashboards
dataset lineage tracking
GPU inference workers
pipeline execution
```

---

# Summary

SignGlove now acts as:

> a developer-focused ML playground for dataset management, model registry, and inference testing.

Training pipelines remain external while the platform focuses on **experiment orchestration and evaluation**.
