# SilentVoix gRPC-Ready Mermaid Pack

Yes, this project can reach gRPC level.  
Your runtime split (`backend` + `ml-tensorflow` + `ml-pytorch` + `worker-library`) is already a strong base for moving internal service-to-service traffic from HTTP/JSON to gRPC.

## 1) Sequence Diagram
```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant FE as Vue Frontend
    participant API as Backend API (FastAPI)
    participant REG as Model Registry (registry.json + Mongo metadata)
    participant RT as Runtime Router
    participant TF as ml-tensorflow Runtime
    participant PT as ml-pytorch Runtime

    U->>FE: Upload model package + run prediction
    FE->>API: POST /playground/models/upload
    API->>REG: Store model metadata + active model
    API-->>FE: Upload success + model_id

    FE->>API: POST /playground/models/{id}/activate
    API->>REG: Set active_model_id
    API-->>FE: Active model updated

    FE->>API: GET /playground/models/{id}/runtime-check
    API->>REG: Read export_format + input_dim
    API->>RT: Resolve target runtime by export_format
    alt TensorFlow family (tflite/keras/h5)
        API->>TF: runtime-check (HTTP now / gRPC target)
        TF-->>API: status=success, output_dim
    else PyTorch family (pth/pt)
        API->>PT: runtime-check (HTTP now / gRPC target)
        PT-->>API: status=success, output_dim
    end
    API-->>FE: Runtime check result

    FE->>API: POST /playground/predict/{cv|sensor}
    API->>RT: Resolve runtime target
    alt TensorFlow model
        API->>TF: predict(input_vector)
        TF-->>API: label/confidence/probabilities
    else PyTorch model
        API->>PT: predict(input_vector)
        PT-->>API: label/confidence/probabilities
    end
    API-->>FE: Stable prediction response schema
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
      +resolve(exportFormat) RuntimeClient
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
    }

    class TensorFlowRuntimeService {
      +runtimeCheck(req)
      +predict(req)
      +health()
    }

    class PyTorchRuntimeService {
      +runtimeCheck(req)
      +predict(req)
      +health()
    }

    FrontendClient --> PlaygroundController
    PlaygroundController --> ModelRegistryService
    PlaygroundController --> RuntimeRouter
    RuntimeRouter --> RuntimeClient
    HTTPRuntimeClient ..|> RuntimeClient
    GRPCRuntimeClient ..|> RuntimeClient
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

    Admin --> (Login / Auth)
    Admin --> (Manage CSV Library)
    Admin --> (Reconcile Model Registry)
    Admin --> (Upload Model Package)
    Admin --> (Activate Model)

    CI --> (Run Runtime Smoke Test)
    (Run Runtime Smoke Test) ..> (Upload Model Package) : includes
    (Run Runtime Smoke Test) ..> (Activate Model) : includes
    (Run Runtime Smoke Test) ..> (Run Runtime Check) : includes
    (Run Runtime Smoke Test) ..> (Realtime Predict CV/Sensor) : includes
```

## 4) Whole-Project Architecture
```mermaid
flowchart LR
    U[User Browser] --> FE[Vue Frontend :5173]
    FE -->|REST/WS| API[Backend API FastAPI :8000]

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

    API -->|runtime-check/predict\nHTTP now, gRPC target| TF
    API -->|runtime-check/predict\nHTTP now, gRPC target| PT
    API -->|reconcile| WK
    TF --> LIB
    PT --> LIB
    WK --> LIB

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
```
