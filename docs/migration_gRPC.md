# gRPC Migration Design Notes

## Purpose
This document describes how to redesign system diagrams and architecture assumptions when migrating internal runtime communication from REST to gRPC.

Current target scope:
- Keep external frontend/backend API as HTTP/JSON.
- Migrate backend-to-runtime service calls to gRPC over HTTP/2.
- Support bi-directional streaming where low-latency inference is needed.

## 1) Sequence Diagram (The "Heartbeat")

### Current (REST pattern)
- Backend sends request.
- Runtime returns response.
- Next frame waits for previous response.

### Target (gRPC bi-directional streaming)
- Open a persistent stream once (`OpenStream()`).
- Keep stream active in a `loop`/`stream` fragment.
- Send and receive concurrently:
  - Backend -> Runtime: `SendSensorData`
  - Runtime -> Backend: `PushPrediction`
- Do not block frame send on prior prediction response.

### Diagram update checklist
- Add explicit stream initialization step.
- Add `loop` block for ongoing stream lifetime.
- Show independent arrows in both directions inside loop.

## 2) System Diagram (The "Backbone")

### Current
- FastAPI <-> Runtime connected as HTTP/REST.

### Target
- FastAPI <-> Runtime labeled `gRPC / HTTP/2`.
- Add shared contract artifact: `sign_glove.proto`.
- If using Triton, runtime node can be:
  - `NVIDIA Triton Inference Server`
  - with multiple model repositories hosted behind it.

### Diagram update checklist
- Replace connector protocol label.
- Add `.proto` as contract source between services.
- Optionally separate inference runtime and model repository blocks.

## 3) Class Diagram (The "Contract")

### Current
- Manual HTTP client + manually defined payload models.

### Target
- gRPC-generated client/stub:
  - `SignGloveStub`
- Protobuf message models:
  - `GloveRequest`
  - `PredictionResponse`
- Service definition:
  - `SignLanguageService`
  - `StreamPredict(stream GloveRequest) returns (stream PredictionResponse)`

### Diagram update checklist
- Replace `HTTPClient` with `*Stub`.
- Replace Pydantic transport models with protobuf message classes.
- Show stream-based service method signatures.

## 4) Use Case Diagram (The "Experience")

Users do not directly see gRPC, but system capabilities and constraints change.

### Additions
- Constraint or sub-use case:
  - `Real-time Translation (< 50ms latency)`
- Secondary operational actors:
  - `Model Monitor`
  - `Triton Optimizer` (if Triton is adopted)

### Diagram update checklist
- Add latency constraint tied to real-time translation use case.
- Add ops/system actors responsible for runtime health and model readiness.

## Comparison Summary

| Feature | REST Design | gRPC Design |
|---|---|---|
| Data Format | JSON (text) | Protobuf (binary) |
| Connection | Short-lived request/response | Persistent stream (optional unary too) |
| Client Call Pattern | `client.post("/predict")` | `stub.Predict(...)` / `stub.StreamPredict(...)` |
| Latency Profile | Higher overhead per call | Lower overhead, better for high-frequency inference |
| Contract Source | API docs + code conventions | `.proto` as source of truth |

## Recommended Migration Style

1. Keep REST for frontend-facing APIs.
2. Introduce gRPC internally between backend and runtime services.
3. Start with unary gRPC equivalents of existing runtime-check/predict.
4. Add bi-directional stream RPC for real-time frame flow.
5. Run dual-stack (HTTP + gRPC) during cutover, then retire internal REST.

## Risks To Track
- Contract drift between REST and gRPC responses.
- Operational complexity (service discovery, retries, deadlines, observability).
- Stream lifecycle errors (disconnect/reconnect/backpressure handling).

## Success Criteria
- Same prediction schema from backend to frontend before/after migration.
- Stable runtime health checks and model load behavior.
- Measurable latency improvement in real-time inference path.

## Phase 2 Execution Checklist

### Milestone 1: Contract Freeze and Proto Design
- [ ] Freeze current internal REST payloads as baseline (`runtime-check`, `predict`, error contract).
- [ ] Create `proto/sign_glove_runtime.proto` with:
  - [ ] `Health` RPC
  - [ ] `RuntimeCheck` RPC
  - [ ] `Predict` RPC
  - [ ] `StreamPredict` RPC (bi-directional)
- [ ] Define canonical error envelope in proto (`code`, `message`, `retryable`).
- [ ] Add versioning strategy (`package runtime.v1`).

Deliverables:
- `.proto` file + generated stubs (not wired yet)
- mapping table REST <-> gRPC fields

Gate:
- backend, `ml-tensorflow`, and `ml-pytorch` agree on proto schema.

### Milestone 2: Runtime Services Dual Transport
- [ ] Add gRPC server to `ml-tensorflow`.
- [ ] Add gRPC server to `ml-pytorch`.
- [ ] Keep existing HTTP endpoints active for fallback.
- [ ] Expose health parity on both transports.

Deliverables:
- gRPC endpoints running in both runtime services
- transport toggle env var in each runtime service

Gate:
- existing HTTP tests still pass.
- gRPC unary calls return equivalent payloads.

### Milestone 3: Backend gRPC Client Integration
- [ ] Add gRPC client layer in backend (`RuntimeClient` abstraction).
- [ ] Implement client methods for `Health`, `RuntimeCheck`, `Predict`.
- [ ] Add feature flag for transport selection (`RUNTIME_TRANSPORT=http|grpc`).
- [ ] Keep response normalization identical to current frontend contract.

Deliverables:
- backend transport abstraction + gRPC implementation
- runtime dispatch unchanged by `export_format`

Gate:
- contract parity tests pass for HTTP and gRPC paths.

### Milestone 4: Streaming Path (Realtime)
- [ ] Implement `StreamPredict` in backend realtime path.
- [ ] Add backpressure/reconnect strategy.
- [ ] Add deadlines and cancellation handling.
- [ ] Add stream metrics (open streams, errors, avg frame latency).

Deliverables:
- stable stream inference loop
- telemetry for stream health

Gate:
- sustained stream test with no memory growth/regression.

### Milestone 5: Observability and Hardening
- [ ] Add structured logs with request/trace IDs across backend+runtimes.
- [ ] Add gRPC timeout/retry policy and circuit-breaker behavior.
- [ ] Add CI coverage for gRPC smoke and parity tests.
- [ ] Add failure artifact upload for gRPC jobs (logs + summary).

Deliverables:
- CI jobs for gRPC smoke
- operations runbook for timeout/error codes

Gate:
- gRPC path is at least as reliable as HTTP in CI.

### Milestone 6: Controlled Cutover
- [ ] Enable `RUNTIME_TRANSPORT=grpc` in staging.
- [ ] Compare latency/error metrics vs HTTP baseline.
- [ ] Enable grpc in production canary.
- [ ] Remove internal REST runtime calls after stable window.

Deliverables:
- cutover report (before/after metrics)
- rollback instructions validated

Gate:
- no schema drift.
- latency target met.
- rollback tested successfully.

## Validation Matrix (Required)
- [ ] Health parity: HTTP vs gRPC
- [ ] RuntimeCheck parity: TF + Torch
- [ ] Predict parity: TF + Torch, CV + Sensor
- [ ] Error mapping parity (`INPUT_DIM_MISMATCH`, `NON_FINITE_INPUT`, etc.)
- [ ] Streaming stability under sustained load
- [ ] Timeout and retry behavior

## Rollback Plan
- Keep runtime HTTP endpoints during migration window.
- Backend transport toggle:
  - primary: `RUNTIME_TRANSPORT=grpc`
  - rollback: `RUNTIME_TRANSPORT=http`
- If gRPC regression occurs:
  1. Switch transport flag back to HTTP.
  2. Keep services running, capture logs/artifacts.
  3. Open fix task with failing payload + trace ID.
