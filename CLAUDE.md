# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

DO NOT RUN SUBAGENTS

## What this is

SilentVoix / V-Hand — a multimodal sign-language recognition platform. An ESP32 glove (MPU6050 + 5 flex sensors) streams sensor frames at 50 Hz over WebSocket, and/or a browser camera produces MediaPipe hand landmarks; models classify the gesture and the frontend speaks the result. It doubles as a "model testing ground": upload a `.tflite`/`.keras`/`.h5`/`.pth`/`.pt` model, validate it, activate it, and run live inference.

## Critical: two parallel Python trees

`api/` and `backend/` are **near-duplicate FastAPI stacks** with the same `core/ routes/ ingestion/ models/ processors/ services/ utils/` layout but divergent file contents. This is the single biggest source of confusion in this repo.

| | `api/` (canonical) | `backend/` (legacy-compatible) |
|---|---|---|
| Imports | absolute — `from api.core.settings import settings` | flat — `from core.settings import settings` |
| Shared code | root-level `services/`, `workers/`, `db/`, `AI/` | its own `backend/services/`, `backend/AI/`, `backend/data/` copies |
| Entrypoint | `uvicorn api.main:app` (port 8000) | `uvicorn main:app` from inside `backend/` (port 8000/8080) |
| Built by | `docker-compose.yml` (`api/Dockerfile`, context = repo root) | `docker-compose.dev.yml` (context = `./backend`) |
| Used by | production compose, Celery workers, Alembic | `run_dev.sh`, dev compose, the CI `backend-runtime-smoke` job |

`docs/transformation.md` §4 declares `api/` + `vue-next/` the canonical stack; `backend/` is legacy unless a module is intentionally reused. **In practice both are live**: `run_dev.sh` and the CI smoke job exercise `backend/`. When changing shared behaviour (routes, settings, services), check whether the same file exists in the other tree and mirror the change or state explicitly that you didn't.

`api/` has code `backend/` lacks: `api/routes/job_routes.py`, and the whole Postgres/Celery layer (`db/`, `workers/`).

## Commands

Frontend (`vue-next/` — the real frontend; root `package.json` is vestigial, no root src/config):

```bash
cd vue-next
npm install
npm run dev          # Vite on :5173
npm run build
npm run lint         # eslint
npm run test         # vitest (watch)
npm run test:run     # vitest single pass — what CI runs
npx vitest run tests/useCollectData.test.js          # single file
npx vitest run -t 'correct initial values'           # single test by name
```

Backend:

```bash
# legacy tree (what run_dev.sh uses)
cd backend && source venv/bin/activate
pip install -r requirements-api.txt          # API-only set: no TensorFlow
uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# canonical tree, from repo root
pip install -r api/requirements.txt
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

./run_dev.sh          # backend + frontend together, logs to logs/*.log
```

Tests:

```bash
cd backend && pytest tests/                                  # pytest.ini sets pythonpath=.
cd backend && pytest tests/test_runtime_contracts.py::test_x  # single test
pytest tests/integration/test_hybrid_foundation.py           # from repo root; needs live Postgres + Mongo
python backend/scripts/smoke_playground_runtime.py --base-url http://localhost:8000
python backend/scripts/smoke_early_fusion_worker.py
```

Test-suite caveats: `backend/tests/test_runtime_contracts.py` imports `routes.playground_routes`, which no longer exists — it is stale and will fail at collection. `test_integrated_v2.py` and `test_video_worker.py` are print-based scripts, not assertion tests, and `test_video_worker.py` requires the early-fusion worker on :8095. CI runs only the frontend suite plus a Docker runtime smoke job.

Docker:

```bash
docker compose up -d --build                             # full stack: nginx FE on :5173, api/, celery, postgres (auto-migrated), mongo, redis, all sidecars
docker compose --profile monitoring up -d                # + prometheus/grafana/celery-exporter
docker compose -f docker-compose.dev.yml up -d            # dev stack (backend/ + mongo)
USE_RUNTIME_SERVICES=true USE_WORKER_LIBRARY=true \
  docker compose -f docker-compose.dev.yml --profile runtime-split up -d --build
docker compose exec api celery -A workers.tasks.celery_app worker --loglevel=info
```

Migrations (Alembic reads `DATABASE_URL` from `api.core.settings`, ignoring the placeholder in `alembic.ini`):

```bash
cd db && alembic upgrade head
cd db && alembic revision --autogenerate -m "message"
```

Ports: frontend 5173 · API 8000 (8080 inside the dev backend container) · ml-tensorflow 8091 · ml-pytorch 8092 · worker-library 8093 · worker-fusion-preprocess 8094 · worker-early-fusion 8095 · Postgres 5432 · Mongo 27017 · Redis 6379.

## Architecture

### Runtime-split inference

The API image deliberately has **no TensorFlow and (in the canonical set) no PyTorch**. Inference is dispatched over HTTP to sidecar FastAPI services, gated by boolean flags in `api/core/settings.py`:

- `USE_RUNTIME_SERVICES` → `ml-tensorflow` (`.tflite`/`.keras`/`.h5`) and `ml-pytorch` (`.pth`/`.pt`)
- `USE_WORKER_LIBRARY` → `worker-library`, which reconciles `registry.json` against files on disk
- `USE_EARLY_FUSION_WORKER` → `worker-early-fusion` (74-dim fused inference)
- `USE_FUSION_PREPROCESS_WORKER` → `worker-fusion-preprocess` (OpenCV video + CSV alignment)

With every flag false, code falls back to in-process paths (`api/core/model.py` loads `LEGACY_TFLITE_MODEL_PATH` only if TF happens to be importable). `api/core/runtime_preflight.py` runs at startup when `RUNTIME_PREFLIGHT_ON_STARTUP` is set and reports library versions plus registry health.

`runtime_adapter.py` (format detection, `load_runtime`, `predict`, extension↔`export_format` validation) exists in **three divergent copies**: `AI/runtime_adapter.py`, `ml-pytorch/runtime_adapter.py`, `ml-tensorflow/runtime_adapter.py`. Each sidecar `COPY`s only its own. Changing validation or output-normalization rules means touching all three.

### Model library / registry

`AI/model_library/registry.json` (`{"models": [...], "active_model_id": ...}`) is the source of truth for uploaded models — a flat JSON file, not a DB table. `services/model_library_service.py` owns it: uploads land in `MODEL_LIBRARY_DIR/<model_id>/model.<ext>`, paths are re-normalized on every registry load, and each entry carries a `runtime_status.state` of `pass`/`fail`/`untested` from `/model-library/models/{id}/runtime-check`. Sidecars mount the same directory read-only at `/shared/model_library`. PyTorch uploads must be **callable inference artifacts** — bare `state_dict` checkpoints are rejected.

### Hybrid storage

- **PostgreSQL** (`db/models.py`, SQLAlchemy 2.0 declarative, Alembic in `db/migrations/`): `users`, `jobs` (`JobRecord`), `datasets`, `models`. `db/base.py` builds both an async engine (FastAPI) and a sync engine (Celery, by rewriting `postgresql+asyncpg://` → `postgresql://`), and switches to `NullPool` when `settings.is_testing()`.
- **MongoDB** (`api/core/database.py`, motor): live sensor sessions, predictions.
- **Redis**: Celery broker/backend plus rate limiting.

### Async job path

Heavy work never blocks the realtime path: a route writes a `JobRecord` row, enqueues a Celery task (`workers/tasks/celery_app.py`, include `workers.tasks.dataset_tasks`), and the worker updates `status`/`progress`/`error_log`/`result_location` through `get_sync_db()`. `api/routes/job_routes.py` joins the Postgres row with live `AsyncResult` state. Note `workers/tasks/dataset_tasks.py` imports `services.datasets.dataset_service`, which exists only under root `services/` — Celery must run from the repo root.

### Live sensor contract

`api/routes/liveWS.py` (`/ws/stream`) accepts several legacy producer shapes and normalizes all of them to `silentvoix.sensor_frame.v1` before anything downstream sees them. The invariant, spelled out in `docs/transformation.md` §8: exactly **11 values ordered `accel[3] + gyro[3] + flex[5]`**, with `timestamp_ms` (producer) and `received_at_ms` (API). Malformed frames are rejected with an error message rather than silently padded. `api/ingestion/streaming/live_data.py` holds the latest frame for polling consumers; the same module also serves broadcast to subscribed browser clients.

Early fusion is a different contract: **30 frames × 74 features (63 CV landmarks + 11 sensor)**, labels `rest,hello,thank_you,yes,no,bye`, sensor order `imu_flex`. `model_fit.py` is the training script that defines it.

### Frontend

Vue 3 + Pinia, no TypeScript. `src/stores/playgroundStore.js` holds playground state and `src/engine/playgroundEngine.js` is the coordinator — it watches modality/live flags to start or stop the sensor stream and clears predictions when the active model changes. Views are thin; the logic lives in `src/composables/` (`ai/useFusionLogic.js` does late-fusion probability blending, `playground/useSensorStream.js` owns the WebSocket). All HTTP goes through the single `src/services/api.js` axios client, which unwraps `response.data` and redirects to `/login` on 401.

`src/views/EmotionStudio.vue` (`/emotion`) is the one inference path that never touches the backend: MediaPipe `face_landmarker` finds the face and the `emotion-ferplus-8` ONNX CNN classifies it via `onnxruntime-web`, both in-tab. Pure logic lives in `src/composables/ai/emotionModel.js` (labels, softmax, crop geometry, EMA smoothing — unit tested), runtime wiring in `src/composables/ai/useFaceEmotion.js`. The 35 MB `.onnx` is gitignored and resolved local-then-CDN; `npm run model:emotion` vendors it into `public/models/emotion/`, `VITE_EMOTION_MODEL_URL` overrides. There is no `api/`/`backend/` counterpart to mirror. `vite.config.js` must keep `onnxruntime-web` in `optimizeDeps.exclude`, or dev-mode pre-bundling breaks its `.wasm` resolution and ORT fails with a wasm "magic number" error (`vite build` is unaffected). See `docs/emotion_recognition.md` — the FER+ class order and the "do not normalise the 0-255 input" rule are both load-bearing.

Two gotchas: modality is inferred from the model's `input_dim` when metadata is missing (11 or 22 ⇒ `sensor`, else `cv`), and `vite.config.js` proxies `/api`, `/ws`, `/auth`, `/static/tts`, `/pics` to `http://backend:8080` — a **Docker service name**. Running `npm run dev` on the host requires setting `VITE_API_URL` (e.g. `http://localhost:8000`) or editing the proxy target.

## Configuration

All settings live in `api/core/settings.py` / `backend/core/settings.py` (pydantic-settings, `extra='ignore'`, so unknown env vars are silently dropped). `env.example` is the reference; `api/` reads `.env` at the repo root, the dev compose backend reads `backend/.env`. `AUTO_SEED_DEFAULT_USERS` seeds admin/editor/guest accounts on startup — keep it off in production.

Frontend-only route: `/emotion` (Emotion Studio) calls no API except the shared TTS route.

Route prefixes: `/auth`, `/gestures`, `/predict`, `/predict/integrated`, `/early-fusion`, `/fusion-preprocess`, `/model-library` (+ `/model-library/feedback`), `/jobs`, `/admin`, `/admin/csv-library`, `/dashboard`, `/capture-controls`, `/audio-files`, `/sync`, `/utils`, `/api/voice`, `/ws`, plus `/health` and `/metrics`.

## Docs worth reading before large changes

- `docs/transformation.md` — V-Hand engineering spec, canonical-stack decision, data contracts
- `docs/README.md` — documentation index and scope rule (docs must describe the current runtime/testing-ground form, not preserved legacy designs)
- `docs/hybrid_database_architecture.md`, `docs/migration_guide.md`
- `docs/agents.md` — competition/QA sprint directives (note: it describes a React frontend; the actual frontend is Vue 3)
