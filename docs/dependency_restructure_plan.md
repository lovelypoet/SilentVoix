# Dependency Restructure Plan (Priority)

## Why This Is Priority
The backend image size issue is a deployment and velocity blocker.
Keeping TensorFlow and PyTorch in one API container increases image size, startup time, memory usage, and operational risk.
This restructure is the correct next step before adding more runtime features.

## Target Outcome
- Split runtime responsibilities so each container installs only what it needs.
- Keep backend API light and stable.
- Keep model prediction support for both TensorFlow and PyTorch, but in separate runtime services.
- Hit practical Docker footprint targets and make size predictable.

## Target Service Architecture
1. `frontend`
2. `backend-api` (FastAPI, auth, model registry, orchestration)
3. `worker-library` (background jobs for model library maintenance)
4. `ml-tensorflow` (TensorFlow runtime inference service)
5. `ml-pytorch` (PyTorch CPU runtime inference service)
6. `database` (MongoDB now, optional PostgreSQL migration later)

## Size Budget (Initial)
- `frontend`: 0.2 to 0.6 GB
- `backend-api`: 0.3 to 0.8 GB
- `worker-library`: 0.2 to 0.6 GB
- `ml-tensorflow`: 1.2 to 2.0 GB
- `ml-pytorch` (CPU): 0.9 to 1.5 GB
- `database`: 0.2 to 0.7 GB (excluding user data volume growth)

Expected total with both ML runtimes enabled: roughly 3.0 to 6.2 GB.

## Progress Snapshot (2026-03-05)
- Runtime split services are present and health-checked:
  - `ml-tensorflow` (`:8091/health`)
  - `ml-pytorch` (`:8092/health`)
  - `worker-library` (`:8093/health`)
- Backend API image uses `requirements-api.txt` in compose dev flow (no TensorFlow/PyTorch in API dependency set).
- Compose startup smoothing completed:
  - `docker-compose.dev.yml` now boots `mongo + backend + frontend` by default.
  - Backend waits for Mongo health before startup.
  - Runtime-split services remain profile-gated (`runtime-split`, `full`, `tf`, `torch`, `worker`).
- End-to-end runtime smoke is automated:
  - local script: `backend/scripts/smoke_playground_runtime.py`
  - CI job: `.github/workflows/test.yml` -> `backend-runtime-smoke`
- Runtime contract unit tests pass locally:
  - `backend/tests/test_runtime_contracts.py` (19 passing tests)

## Scope Rules
In scope:
- dependency split and runtime service boundaries
- backend runtime dispatch (TF vs Torch)
- model registry and runtime-check integration across services
- Docker compose profiles and separate Dockerfiles

Out of scope for this phase:
- new training pipeline features
- major UI redesign unrelated to runtime split
- database migration (can be planned separately)

## Dependency Boundaries
`backend-api` must not install:
- tensorflow
- torch

`ml-tensorflow` installs:
- tensorflow/keras stack and minimal serving deps

`ml-pytorch` installs:
- torch CPU wheel and minimal serving deps

`worker-library` installs:
- storage/validation/background job deps only
- no heavy ML runtimes unless explicitly required for a background task

## Runtime Routing Contract
- Model metadata includes `export_format` and `modality`.
- API runtime dispatcher selects target service by `export_format`:
  - TensorFlow family (`.tflite`, `.keras`, `.h5`) -> `ml-tensorflow`
  - PyTorch family (`.pth`, `.pt`) -> `ml-pytorch`
- API keeps response schema stable for frontend regardless of backend runtime.

## Rollout Phases
1. Define service contracts
- request/response schema for runtime-check and predict
- failure contract and timeout contract

2. Extract backend API deps
- remove tensorflow/torch from `backend-api` requirements
- keep backend runtime-agnostic

3. Build `ml-tensorflow` service
- implement load, runtime-check, predict endpoints
- ensure health endpoint

4. Build `ml-pytorch` service
- implement load, runtime-check, predict endpoints
- enforce callable artifact validation

5. Build `worker-library` service
- move model-library maintenance/background logic here
- keep API synchronous paths clean

6. Integrate compose profiles
- `profile tf`, `profile torch`, `profile full`
- allow running one runtime or both

7. Validation and hardening
- contract tests for all runtime endpoints
- latency and failure-path verification
- image size verification per service

## Success Criteria
- Backend API container does not include TensorFlow/PyTorch packages.
- Predictions work for both TF and Torch models through runtime services.
- Runtime-check updates model `runtime_status` reliably.
- Frontend behavior remains unchanged.
- Total stack size is within planned budget.

## Risks and Controls
- Risk: contract drift between runtime services.
  - Control: shared schema tests and compatibility tests.

- Risk: operational complexity from more services.
  - Control: strict compose profiles and clear health checks.

- Risk: latency overhead from inter-service calls.
  - Control: warm model caches in runtime services and timeout strategy.

## Immediate Next Actions
1. Simplify legacy TFLite/training-era defaults in backend settings where no longer required.
2. Add image-size verification checks into CI or release checklist.
3. Add CI artifacts for runtime smoke logs for faster failure triage.

## Run Profiles (Current)
- `tf`: runs tensorflow runtime service.
- `torch`: runs pytorch runtime service.
- `worker`: runs model-library reconcile worker.
- `runtime-split`: runs both runtimes plus worker.
- `full`: same as runtime-split (for now).

## Decision
This dependency restructure is now the active priority phase.
