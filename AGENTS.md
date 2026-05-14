# SilentVoix — Agent Guide

Monorepo: sign-glove model testing ground (not training). FastAPI backend + Vue 3 frontend + Docker ML microservices.

## Quick Commands

| What | Command |
|------|---------|
| Start dev (backend + frontend) | `./run_dev.sh` |
| Backend API only | `cd backend && python main.py` (or `uvicorn main:app --reload --port 8000`) |
| Frontend dev | `cd vue-next && npm run dev` |
| Frontend test (watch) | `npm run test` |
| Frontend test (single) | `npm run test:run` |
| Frontend lint | `npm run lint` |
| Frontend format check | `npm run format` |
| Backend test | `cd backend && pip install -r requirements-dev.txt && pytest tests/` |
| Backend smoke test | `python backend/scripts/smoke_playground_runtime.py --base-url http://localhost:8000` |
| Docker dev stack | `USE_RUNTIME_SERVICES=true USE_WORKER_LIBRARY=true docker compose -f docker-compose.dev.yml --profile runtime-split up -d` |

## Architecture

- **`backend/`** — FastAPI entrypoint (`main.py`), routes in `routes/`, core logic in `core/`, services in `services/`
- **`vue-next/`** — Vite + Vue 3 + Pinia + PrimeVue + Tailwind
- **`ml-tensorflow/`** / **`ml-pytorch/`** — standalone inference microservices (ports 8091/8092)
- **`worker-library/`** — model registry reconciliation (port 8093)
- **`worker-early-fusion/`** / **`worker-fusion-preprocess/`** — fusion workers (ports 8095/8094)
- **`db/`** — Alembic migrations + SQLAlchemy models (PostgreSQL)
- **`workers/tasks/`** — Celery background tasks
- **`monitoring/`** — Prometheus + Grafana configs

## Key Config & Conventions

- The backend API container uses `requirements-api.txt` which has **no TensorFlow/PyTorch** — inference forwards to ml-tensorflow/ml-pytorch over HTTP.
- Copy `env.example` to `backend/.env` for local config.
- Python 3.11.9 (`.python-version`), Node.js 20 (CI), Vue 3 + Vite 7.
- PyTorch uploads must be **callable inference artifacts**, not `state_dict`-only. Provide `model.py` class file + `is_state_dict=true` flag if needed.
- Model artifacts live at `backend/AI/model_library/{model_id}/` with `registry.json`.
- Vite dev proxy: `/api`, `/ws`, `/auth`, `/static/tts`, `/pics` → `http://backend:8080` (Docker hostname).
- MongoDB is primary; PostgreSQL + Redis are required for full stack.
- Default seeded users: admin/admin123, editor/editor123, user/user123 (controlled by env flags).
- Startup runs runtime preflight (health checks on all ML services + registry) if `RUNTIME_PREFLIGHT_ON_STARTUP=true`.
- CI: frontend build+test, super-linter (vue-next/src only), backend runtime smoke (Docker compose).
- Backend pytest config: `backend/pytest.ini` with `asyncio_default_fixture_loop_scope = function`.

## Supported Model Formats

`.tflite`, `.keras`, `.h5`, `.pth`, `.pt` — mapped to runtimes: `tflite`/`tensorflow-lite` → ml-tensorflow, `keras`/`h5` → ml-tensorflow, `pytorch`/`torch`/`pth` → ml-pytorch.

## Dev URLs

| Service | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| TensorFlow runtime | http://localhost:8091 |
| PyTorch runtime | http://localhost:8092 |
| Worker library | http://localhost:8093 |
| Fusion preprocess | http://localhost:8094 |
| Early fusion | http://localhost:8095 |
