# SilentVoix gRPC Migration Mermaid Pack

Aligned with `docs/migration_gRPC.md` Phase 2 plan:
- external API remains REST/WS
- internal runtime calls move HTTP -> gRPC (dual-stack first)
- `RUNTIME_TRANSPORT=http|grpc` controls backend runtime transport

## 1) Sequence Diagram
```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant FE as Vue Frontend
    participant API as Backend API (FastAPI)
    participant REG as Model Registry
    participant RTR as Runtime Router
    participant TF as ml-tensorflow
    participant PT as ml-pytorch

    U->>FE: Upload model package + run prediction
    FE->>API: POST /playground/models/upload
    API->>REG: Store model metadata + active model
    API-->>FE: Upload success + model_id

    FE->>API: POST /playground/models/{id}/activate
    API->>REG: Set active_model_id
    API-->>FE: Active model updated

    FE->>API: GET /playground/models/{id}/runtime-check
    API->>REG: Read export_format + input_dim
    API->>RTR: resolve(export_format, RUNTIME_TRANSPORT)
    alt TensorFlow family (tflite/keras/h5)
        API->>TF: RuntimeCheck (HTTP or gRPC unary)
        TF-->>API: status=success, output_dim
    else PyTorch family (pth/pt)
        API->>PT: RuntimeCheck (HTTP or gRPC unary)
        PT-->>API: status=success, output_dim
    end
    API-->>FE: Runtime check result

    FE->>API: POST /playground/predict/{cv|sensor}
    API->>RTR: resolve(export_format, RUNTIME_TRANSPORT)
    alt TensorFlow model
        API->>TF: Predict (HTTP or gRPC unary)
        TF-->>API: label/confidence/probabilities
    else PyTorch model
        API->>PT: Predict (HTTP or gRPC unary)
        PT-->>API: label/confidence/probabilities
    end
    API-->>FE: Stable prediction response schema

    Note over API,PT: Phase 2 streaming path (realtime)
    API->>PT: OpenStream(StreamPredict)
    loop while stream alive
      API-->>PT: SendSensorData frame_n
      PT-->>API: PushPrediction frame_n
    end
```

## 2) Class Diagram
```mermaid
classDiagram
    class FrontendClient {
      +uploadModel(file, metadata)
      +activateModel(modelId)
      +runtimeCheck(modelId)
      +predictCV(values)
      +predictSensor(values)
    }

    class PlaygroundController {
      +uploadModel()
      +activateModel()
      +runtimeCheck()
      +predictCV()
      +predictSensor()
    }

    class ModelRegistryService {
      +loadRegistry()
      +saveRegistry()
      +setActive(modelId)
      +getActive()
      +getModel(modelId)
    }

    class RuntimeRouter {
      +resolve(exportFormat, transport) RuntimeClient
    }

    class RuntimeClient {
      <<interface>>
      +runtimeCheck(payload)
      +predict(payload)
      +health()
    }

    class HTTPRuntimeClient {
      +runtimeCheck(payload)
      +predict(payload)
      +health()
    }

    class GRPCRuntimeClient {
      +runtimeCheck(payload)
      +predict(payload)
      +health()
      +streamPredict(streamPayload)
    }

    class RuntimeTransportPolicy {
      +transport: http|grpc
      +fallback: http
    }

    class ProtoContract {
      +sign_glove_runtime.proto
      +RuntimeCheckRequest/Response
      +PredictRequest/Response
      +StreamPredict(stream)
    }

    class TensorFlowRuntimeService {
      +runtimeCheck(req)
      +predict(req)
      +streamPredict(reqStream)
      +health()
    }

    class PyTorchRuntimeService {
      +runtimeCheck(req)
      +predict(req)
      +streamPredict(reqStream)
      +health()
    }

    FrontendClient --> PlaygroundController
    PlaygroundController --> ModelRegistryService
    PlaygroundController --> RuntimeRouter
    RuntimeRouter --> RuntimeTransportPolicy
    RuntimeRouter --> RuntimeClient
    HTTPRuntimeClient ..|> RuntimeClient
    GRPCRuntimeClient ..|> RuntimeClient
    GRPCRuntimeClient --> ProtoContract
    HTTPRuntimeClient --> TensorFlowRuntimeService
    HTTPRuntimeClient --> PyTorchRuntimeService
    GRPCRuntimeClient --> TensorFlowRuntimeService
    GRPCRuntimeClient --> PyTorchRuntimeService
```

## 3) Use Case Diagram
```mermaid
usecaseDiagram
    actor Viewer
    actor Editor
    actor Admin
    actor CI as CI Pipeline

    rectangle SilentVoix {
      (Login / Auth)
      (Upload Model Package)
      (Activate Model)
      (Run Runtime Check)
      (Realtime Predict CV/Sensor)
      (View Monitoring Dashboard)
      (Manage CSV Library)
      (Run Runtime Smoke Test)
      (Inspect Service Health)
      (Reconcile Model Registry)
      (Meet Realtime SLA < 50ms)
      (Select Runtime Transport)
      (Rollback to HTTP Transport)
    }

    Viewer --> (Login / Auth)
    Viewer --> (View Monitoring Dashboard)
    Viewer --> (Realtime Predict CV/Sensor)

    Editor --> (Login / Auth)
    Editor --> (Upload Model Package)
    Editor --> (Activate Model)
    Editor --> (Run Runtime Check)
    Editor --> (Realtime Predict CV/Sensor)
    Editor --> (Inspect Service Health)
    Editor --> (Meet Realtime SLA < 50ms)

    Admin --> (Login / Auth)
    Admin --> (Manage CSV Library)
    Admin --> (Reconcile Model Registry)
    Admin --> (Upload Model Package)
    Admin --> (Activate Model)
    Admin --> (Select Runtime Transport)
    Admin --> (Rollback to HTTP Transport)

    CI --> (Run Runtime Smoke Test)
    (Run Runtime Smoke Test) ..> (Upload Model Package) : includes
    (Run Runtime Smoke Test) ..> (Activate Model) : includes
    (Run Runtime Smoke Test) ..> (Run Runtime Check) : includes
    (Run Runtime Smoke Test) ..> (Realtime Predict CV/Sensor) : includes
    (Rollback to HTTP Transport) ..> (Select Runtime Transport) : extends
```

## 4) Whole-Project Architecture
```mermaid
flowchart LR
    U[User Browser] --> FE[Vue Frontend :5173]
    FE -->|REST/WS| API[Backend API FastAPI :8000]
    API --> CFG[[RUNTIME_TRANSPORT=http|grpc]]

    subgraph DataPlane[Data & Storage]
      MDB[(MongoDB :27017)]
      LIB[(Model Library Volume\nbackend/AI/model_library)]
    end

    API --> MDB
    API --> LIB

    subgraph RuntimeSplit[Runtime Split Services]
      TF[ml-tensorflow :8091]
      PT[ml-pytorch :8092]
      WK[worker-library :8093]
    end

    API -->|runtime-check/predict\nHTTP (fallback)| TF
    API -->|runtime-check/predict\nHTTP (fallback)| PT
    API -->|runtime-check/predict\ngRPC over HTTP/2| TF
    API -->|runtime-check/predict\ngRPC over HTTP/2| PT
    API -->|reconcile| WK
    TF --> LIB
    PT --> LIB
    WK --> LIB

    PROTO[[sign_glove_runtime.proto]]
    PROTO -. shared contract .- API
    PROTO -. shared contract .- TF
    PROTO -. shared contract .- PT

    subgraph HardwareIO[Optional Device/IO]
      DEV[/Serial /dev/ttyACM0/]
      TTS[TTS Provider]
    end
    API --- DEV
    API --- TTS

    CI[GitHub Actions\nbackend-runtime-smoke] -->|docker compose runtime-split| API
    CI --> TF
    CI --> PT
    CI --> WK
    CI --> ART[(smoke log artifacts)]
```
