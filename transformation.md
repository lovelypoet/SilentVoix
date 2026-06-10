# SilentVoix V-Hand Transformation Spec

Status: Draft engineering spec
Target milestone: May 17, 2026
Primary goal: competition-ready local sign-glove inference demo

## 1. Purpose

This document defines the practical transformation of SilentVoix into a focused `V-Hand` demo system:

- one right-hand ESP32 glove
- live sensor streaming
- local or local-network inference
- browser feedback with low latency
- optional text-to-speech

This is not a broad platform roadmap. It is the implementation contract for a stable demo build inside the current repository.

## 2. Product Statement

`V-Hand: Your Hand, Your Voice`

The system converts right-hand glove motion and flex sensor readings into live gesture predictions, then displays the prediction in the frontend and optionally plays voice output.

Success means:

- the glove streams reliably
- the backend accepts and normalizes frames
- the frontend shows current system state
- predictions update in real time
- the demo can run offline on the local machine and local network

## 3. Repository Reality

The current repo is a monorepo with overlapping stacks. This spec defines which parts are the target path for the V-Hand demo.

Relevant existing paths:

- `api/` - current FastAPI application entrypoint and route set
- `backend/` - older parallel FastAPI stack with similar structure
- `api/routes/liveWS.py` - existing live WebSocket stream endpoint
- `api/models/sensor_models.py` - current stored sensor session model
- `ml-tensorflow/` - TensorFlow/TFLite runtime microservice
- `ml-pytorch/` - PyTorch runtime microservice
- `worker-library/` - model registry reconciliation service
- `vue-next/` - Vue 3 frontend

## 4. Decision: Canonical Stack

For the competition build, the canonical application stack is:

- API server: `api/`
- frontend: `vue-next/`
- runtime inference: local model in-process when lightweight enough, otherwise existing runtime services
- live stream transport: WebSocket via `api/routes/liveWS.py`

The `backend/` tree is treated as legacy-compatible code unless a specific module is still required and intentionally reused.

## 5. In Scope

- right-hand glove only
- MPU6050 + 5 flex sensors
- serial or websocket ingestion from ESP32 bridge
- real-time prediction
- gesture-to-text output
- optional TTS playback
- frontend connection and latency indicators
- minimal recovery from disconnects and malformed frames

## 6. Out of Scope

- camera-based tracking
- MediaPipe-based gesture extraction
- Triton deployment
- gRPC transport
- distributed inference orchestration
- multi-user scale concerns
- cloud inference dependency
- training pipeline redesign

## 7. Target Architecture

### 7.1 Data flow

1. ESP32 glove samples sensors at 50 Hz.
2. Frames are sent to the host bridge.
3. The bridge forwards frames to the API over WebSocket.
4. The API normalizes every frame into one canonical schema.
5. The latest frame is stored for live consumers.
6. The inference path consumes the canonical frame or a short rolling window.
7. Prediction results are broadcast to the frontend.
8. The frontend renders label, confidence, status, and optional voice output.

### 7.2 Component ownership

ESP32 producer

- read sensors
- apply sensor calibration
- produce stable frame stream

`api/routes/liveWS.py`

- accept producer websocket connection
- parse producer payloads
- normalize legacy shapes to canonical schema
- keep latest live frame
- broadcast live frames to subscribed clients

`api/ingestion/streaming/live_data.py`

- store latest normalized values for simple polling consumers

Inference service layer

- consume normalized frames
- run classification
- return label and confidence
- expose failure state cleanly

`vue-next/`

- show connection state
- show latest prediction
- show confidence and latency
- trigger optional TTS

## 8. Canonical Live Sensor Contract

The current code already accepts multiple payload shapes in `api/routes/liveWS.py`. For the V-Hand demo, one canonical live frame schema must be treated as the source of truth.

### 8.1 Canonical producer message

Preferred producer payload:

```json
{
  "type": "sensor_frame_v1",
  "session_id": "demo-session-001",
  "source": "esp32-serial-bridge",
  "timestamp_ms": 1715640000000,
  "frame": {
    "flex": [0.11, 0.52, 0.88, 0.73, 0.14],
    "accel": [-0.01, 0.98, 0.04],
    "gyro": [0.21, -0.12, 0.03]
  }
}
```

### 8.2 Canonical normalized backend message

`api/routes/liveWS.py` currently normalizes outgoing values into this order:

`accel[3] + gyro[3] + flex[5]`

Canonical normalized payload:

```json
{
  "type": "sensor_frame",
  "schema": "silentvoix.sensor_frame.v1",
  "schema_version": "1.0",
  "session_id": "demo-session-001",
  "source": "esp32-serial-bridge",
  "timestamp_ms": 1715640000000,
  "received_at_ms": 1715640000035,
  "channels": {
    "flex": [0.11, 0.52, 0.88, 0.73, 0.14],
    "accel": [-0.01, 0.98, 0.04],
    "gyro": [0.21, -0.12, 0.03]
  },
  "values": [-0.01, 0.98, 0.04, 0.21, -0.12, 0.03, 0.11, 0.52, 0.88, 0.73, 0.14]
}
```

### 8.3 Rules

- exactly 11 sensor values per frame
- flex count must be 5
- accel count must be 3
- gyro count must be 3
- `timestamp_ms` is producer event time
- `received_at_ms` is API receive time
- malformed payloads are rejected and answered with an error message
- legacy payload shapes remain accepted during migration, but all downstream processing uses the canonical normalized shape

## 9. Stored Session Data Contract

For persisted gesture sessions, the current canonical model is `api/models/sensor_models.py`.

Stored session shape:

- `session_id: str`
- `timestamp: datetime`
- `sensor_values: List[List[float]]`
- `gesture_label: Optional[str]`
- `device_info.source: str`
- `device_info.device_id: Optional[str]`

Constraint for this V-Hand path:

- each inner `sensor_values` entry must contain 11 floats in canonical order

This document does not change the persisted storage model. It only clarifies that live and stored data must use the same 11-value ordering.

## 10. Inference Contract

The previous draft assumed single-frame inference. That is not safe as a hard requirement. This spec allows either:

- single-frame classification, if the deployed model was trained that way
- short rolling-window classification, if the deployed model expects temporal input

The model contract must be documented per deployed artifact:

- input shape
- expected value order
- normalization assumptions
- output labels
- output confidence format

### 10.1 Preferred runtime order

1. use the existing runtime-service architecture when the model artifact already fits it
2. allow in-process local inference only for lightweight demo-safe models
3. avoid introducing a new runtime stack unless existing `ml-tensorflow/` or `ml-pytorch/` cannot satisfy the demo path

### 10.2 Prediction result contract

Canonical prediction result:

```json
{
  "type": "prediction",
  "session_id": "demo-session-001",
  "timestamp_ms": 1715640000040,
  "label": "hello",
  "confidence": 0.93,
  "model_id": "active-model-id",
  "latency_ms": 37,
  "source_frame_timestamp_ms": 1715640000000
}
```

If prediction fails, the system must emit a structured error status rather than silently stalling.

## 11. Transport and Concurrency Model

### 11.1 Live transport

Primary live transport:

- producer to API: WebSocket to `/ws/stream`
- API to frontend consumers: WebSocket broadcast from `/ws/stream`

### 11.2 Concurrency requirements

The system does not need a complex thread diagram in the spec. It needs concrete guarantees:

- live sensor ingest must not block the FastAPI event loop for long-running inference
- prediction work must run outside the websocket receive hot path if inference latency becomes noticeable
- frontend broadcast must continue even if one client disconnects
- latest frame state must stay readable by low-cost polling endpoints

Implementation may use:

- async tasks
- worker threads
- runtime service HTTP calls

The implementation choice is acceptable if it meets the latency and stability targets below.

## 12. Frontend Contract

The frontend in `vue-next/` must render the demo as an intentional live system, not just raw values.

Required UI elements:

- product label: `V-Hand`
- slogan: `Your Hand, Your Voice`
- live connection state
- latest gesture label
- confidence score
- latency indicator
- voice output state

Required UI states:

- `DISCONNECTED` - no backend or producer connection
- `CONNECTING` - websocket or backend handshaking
- `STREAMING` - live frames are arriving
- `PREDICTING` - model inference active
- `ERROR` - recoverable or user-visible failure

## 13. Failure Handling

### 13.1 Producer disconnect

- mark stream stale if no frame arrives within a configured timeout
- expose stale state to frontend
- retry bridge connection automatically

### 13.2 Malformed frames

- reject frame
- log the error with payload shape detail when safe
- keep stream alive

### 13.3 Inference failure

- return structured error state
- do not crash websocket handling
- continue accepting frames after recovery

### 13.4 Frontend disconnect

- websocket reconnect with backoff
- restore normal operation without server restart

## 14. Performance Targets

These are demo acceptance targets, not general product SLAs.

| Component | Target |
|---|---|
| Sensor sample interval | 20 ms nominal / 50 Hz |
| API ingest and normalization | < 10 ms per frame |
| Inference latency | < 40 ms median |
| Frame-to-UI update | < 120 ms end-to-end |
| Sustained demo runtime | 10 minutes without manual recovery |

Measurement notes:

- end-to-end latency should be measured from producer `timestamp_ms` to prediction or UI update timestamp
- latency should be logged in a form visible during demo validation

## 15. Migration Plan

### 15.1 Keep

- `api/` as the canonical application path
- `vue-next/`
- existing runtime microservices if the active model depends on them
- model library and registry flow where already working

### 15.2 Adapt

- `api/routes/liveWS.py` becomes the canonical live ingest and broadcast route
- prediction flow should consume canonical normalized frames
- frontend should subscribe to one documented live stream contract

### 15.3 De-emphasize or retire from the V-Hand path

- `backend/` as a parallel app surface
- Triton-oriented assumptions
- gRPC-specific flows
- MediaPipe- or camera-oriented paths
- distributed inference features not needed for the demo

This does not require immediate deletion. It means these paths are not on the critical path for the competition build.

## 16. Immediate Implementation Sequence

Phase 1

- lock the canonical live sensor schema
- verify producer sends correct channel counts and ordering

Phase 2

- wire prediction flow from normalized live frames
- define and emit canonical prediction payloads

Phase 3

- connect frontend to live stream and prediction states
- render connection, prediction, confidence, and latency

Phase 4

- validate the active model contract
- confirm whether input is single-frame or rolling-window

Phase 5

- add optional TTS trigger path
- tune reconnect and stale-state behavior

Phase 6

- run a full demo rehearsal and collect latency evidence

## 17. Acceptance Criteria

The V-Hand competition build is considered ready when all of the following are true:

- the glove streams 11-value frames consistently at the target rate
- the API accepts producer frames through `/ws/stream`
- normalized frames use one documented canonical ordering
- live predictions appear in the frontend within target latency
- disconnects and malformed frames do not require a full app restart
- the UI clearly communicates `V-Hand: Your Hand, Your Voice`
- the system can be demonstrated locally without cloud dependency

## 18. Open Questions

These must be answered before locking implementation:

- Which deployed model artifact is the competition model?
- Does that model expect one frame or a temporal window?
- Will prediction run in-process or through `ml-tensorflow` / `ml-pytorch`?
- Is the ESP32 bridge sending raw serial to a host-side bridge script, or sending websocket messages directly?
- Which frontend route or page is the dedicated competition demo surface?

Answer:
1. LSTM

2. Temporal

3. both

4. The esp bridge should send to a point the can be preprocessed just like the training code of the model(read the model_fit.py)

5. Remake the playground page 

## 19. Non-Goals for This Document

This document does not define:

- training methodology
- dataset labeling policy
- long-term production architecture
- broad repository cleanup beyond the competition path
