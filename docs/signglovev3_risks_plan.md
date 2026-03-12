# SignGlove V3 – Architecture Risks & Best Practices Review

This document summarizes **three critical architectural pitfalls** that commonly break ML platforms at scale and the recommended patterns to avoid them.
It is intended to review the **SignGlove V3 architecture** with AI coding assistants or collaborators.

---

# 1. Artifact Chaos (Model Versioning Problem)

## Problem

Without a strict artifact versioning strategy, model storage quickly becomes disorganized:

```
models/
   final.pt
   final2.pt
   best.pt
   best_new.pt
   latest_final.pt
```

After some time it becomes impossible to determine:

* which model generated which results
* which dataset trained the model
* which version is currently deployed
* which model should be used for inference

This leads to **reproducibility failure** and **debugging nightmares**.

---

## Recommended Architecture

Use **immutable model versioning**.

```
storage/
   models/
      gesture_lstm/
         v1/
            model.pt
            metadata.json
         v2/
            model.pt
            metadata.json
```

Each version folder is **immutable**.

Workers must **never overwrite existing versions**.

---

## Metadata Example

```
{
  "model_name": "gesture_lstm",
  "version": "v2",
  "dataset": "asl_dataset_v3",
  "framework": "pytorch",
  "accuracy": 0.94,
  "created_at": "2026-03-12"
}
```

---

## Database Pointer Strategy

Instead of replacing files:

```
model_name: gesture_lstm
active_version: v2
```

Workers:

1. Create new version folder
2. Upload artifacts
3. Update DB pointer

This prevents:

* artifact corruption
* race conditions
* accidental overwrites

---

# 2. Worker Explosion

## Problem

When asynchronous jobs are introduced, developers often move **every operation** into workers:

```
parse_dataset
train_model
run_inference
compute_metrics
validate_dataset
generate_preview
```

Eventually a single worker process handles everything.

This creates:

* queue starvation
* unpredictable latency
* memory leaks
* hard debugging

---

## Recommended Pattern – Worker Specialization

Instead of a single generic worker:

```
worker
```

Use **specialized workers**:

```
dataset-worker
inference-worker
metrics-worker
```

---

## Example Responsibilities

### Dataset Worker

Handles:

```
CSV parsing
dataset validation
dataset preprocessing
```

Queue:

```
dataset_queue
```

---

### Inference Worker

Handles:

```
batch inference
prediction generation
model evaluation
```

Queue:

```
inference_queue
```

---

### Metrics Worker

Handles:

```
precision calculation
recall calculation
f1-score computation
analytics
```

Queue:

```
metrics_queue
```

---

## Benefits

* shorter jobs are not blocked by long jobs
* easier scaling
* easier debugging
* better system stability

---

# 3. API Orchestration Overload

## Problem

Many ML systems gradually turn the API into a **central orchestration engine**.

Example flow:

```
API
 ├ call dataset worker
 ├ call inference worker
 ├ call metrics worker
 ├ call storage
 └ call ML runtime
```

This creates a **distributed monolith**.

Consequences:

* cascading failures
* complex debugging
* long request latency
* API instability

---

## Recommended Pattern – Event Driven Pipeline

The API should only **enqueue jobs**.

Example:

```
Client
   │
API Gateway
   │
enqueue job
   │
Worker pipeline
```

---

## Example Workflow

```
dataset uploaded
     ↓
dataset_worker
     ↓
dataset_validated event
     ↓
inference_worker
     ↓
metrics_worker
```

The API returns immediately:

```
{
  "job_id": "abc123"
}
```

The pipeline completes asynchronously.

---

# 4. Bonus Risk – Model Loading Latency

## Problem

A common mistake in inference services:

```
def predict():
    model = load_model("model.pt")
    return model(x)
```

This loads the model **for every request**, causing latency of several seconds.

---

## Correct Pattern

Load model once during service startup.

```
model = load_model("model.pt")

def predict():
    return model(x)
```

Benefits:

* low latency
* predictable performance
* reduced I/O overhead

---

# 5. Recommended Future Improvements

To evolve SignGlove into a full **ML platform**, consider adding:

```
experiment tracking
dataset versioning
model registry abstraction
pipeline orchestration
artifact storage using S3/MinIO
observability (Prometheus + Grafana)
```

---

# 6. Target Architecture

```
Frontend
   │
API Gateway
   │
Service Layer
   │
Task Queue (Redis)
   │
Workers
   │
ML Runtime Services
   │
Artifact Storage
   │
Metadata Database
```

This architecture aligns with modern ML platforms such as:

* MLflow
* Kubeflow
* BentoML
* Metaflow

---

# Summary

To maintain long-term stability of the SignGlove system:

1. Use **immutable artifact versioning**
2. Implement **specialized workers**
3. Avoid **API orchestration overload**
4. Ensure **models are loaded once per runtime**

Following these principles will allow the system to scale while remaining maintainable.
