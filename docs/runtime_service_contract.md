# Runtime Service Contract

## Purpose
Define the internal API contract between `backend-api` and runtime services:
- `ml-tensorflow`
- `ml-pytorch`

This contract keeps frontend behavior stable while allowing backend runtime split.

## Service Roles
- `backend-api`: source of truth for registry/activation/auth; dispatches inference calls.
- runtime service: loads model artifact, validates runtime, executes inference.

## Transport
- Protocol: HTTP/JSON
- Network: internal Docker network only
- Authentication: internal-only first phase (token optional later)
- Timeout defaults:
  - connect timeout: 2s
  - request timeout: 10s (`runtime-check`), 5s (`predict`)

## Shared Definitions

### `export_format` families
- TensorFlow runtime: `tflite`, `keras`, `h5`
- PyTorch runtime: `pytorch`

### `modality`
- `cv`
- `sensor`

### Input vector
- `float[]`, finite numeric only
- must match model `input_dim`

## Endpoints

### 1) `GET /health`
Used by compose health checks and backend warmup.

Response `200`:
```json
{
  "status": "ok",
  "service": "ml-tensorflow",
  "runtime": "tensorflow",
  "version": "1.0"
}
```

### 2) `POST /v1/runtime-check`
Performs model load + dry-run inference using zero input vector.

Request:
```json
{
  "model_id": "uuid",
  "model_path": "/shared/model_library/<id>/model.pth",
  "export_format": "pytorch",
  "input_dim": 11,
  "labels": ["hello", "thanks"],
  "modality": "sensor"
}
```

Response `200`:
```json
{
  "status": "success",
  "model_id": "uuid",
  "runtime": "pytorch",
  "input_dim": 11,
  "output_dim": 2,
  "message": "Runtime load and dry-run inference succeeded"
}
```

Error example `422`:
```json
{
  "status": "error",
  "code": "INPUT_DIM_MISMATCH",
  "message": "input_dim must be > 0",
  "retryable": false
}
```

### 3) `POST /v1/predict`
Runs one inference and returns normalized probabilities.

Request:
```json
{
  "model_id": "uuid",
  "model_path": "/shared/model_library/<id>/model.keras",
  "export_format": "keras",
  "input_dim": 63,
  "labels": ["A", "B", "C"],
  "modality": "cv",
  "input_vector": [0.01, 0.02, 0.03]
}
```

Response `200`:
```json
{
  "status": "success",
  "model_id": "uuid",
  "prediction": {
    "label": "B",
    "confidence": 0.91,
    "probabilities": {
      "A": 0.04,
      "B": 0.91,
      "C": 0.05
    },
    "top3": [
      {"label": "B", "confidence": 0.91},
      {"label": "C", "confidence": 0.05},
      {"label": "A", "confidence": 0.04}
    ]
  }
}
```

Error example `400`:
```json
{
  "status": "error",
  "code": "NON_FINITE_INPUT",
  "message": "input_vector contains non-finite values",
  "retryable": false
}
```

## Error Contract
All runtime errors must return:
```json
{
  "status": "error",
  "code": "ERROR_CODE",
  "message": "human readable",
  "retryable": false
}
```

### Suggested codes
- `MODEL_NOT_FOUND`
- `UNSUPPORTED_EXPORT_FORMAT`
- `INVALID_MODEL_ARTIFACT`
- `STATE_DICT_ONLY_ARTIFACT`
- `INPUT_DIM_MISMATCH`
- `NON_FINITE_INPUT`
- `EMPTY_OUTPUT`
- `NON_FINITE_OUTPUT`
- `RUNTIME_LOAD_FAILED`
- `RUNTIME_PREDICT_FAILED`
- `TIMEOUT`

## Backend Dispatch Rules
1. Read model metadata from registry.
2. Map `export_format` to runtime service:
   - TF family -> `ml-tensorflow`
   - `pytorch` -> `ml-pytorch`
3. Send identical contract payload regardless of runtime.
4. Normalize runtime errors into existing API response style.
5. Preserve current frontend response schema from `/playground/predict/*`.

## Caching Expectations
- Runtime service may cache loaded models in-process by `(model_id, mtime)`.
- Cache invalidates automatically when file mtime changes.
- Cache eviction policy: LRU (optional in phase 1, required in phase 2).

## Compatibility Rules
- `backend-api` is contract owner.
- Runtime services must be backward compatible for one release window.
- Any contract change requires:
  - doc update
  - contract test update
  - version bump in runtime service (`/health.version`)

## Test Matrix (Minimum)
1. TF runtime-check success (`.tflite`)
2. TF predict success (`.keras/.h5`)
3. Torch runtime-check success (`.pth/.pt` callable)
4. Torch reject state_dict-only artifact
5. input dim mismatch handling
6. non-finite input handling
7. output normalization validity
8. timeout handling from backend-api

## Phase-1 Non-Goals
- gRPC transport
- async queue inference
- autoscaling policies
- GPU runtime split

