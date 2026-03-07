# SilentVoix

SilentVoix is a sign-glove platform centered on a **multi-format model testing ground**. The current product scope is model upload, storage, activation, runtime validation, and live inference, not in-app model training.

## Current Scope

- Upload exported model packages for playground inference.
- Support curated runtime formats: `.tflite`, `.keras`, `.h5`, `.pth`, `.pt`.
- Run runtime preflight checks before activation or live testing.
- Stream sensor and camera input into the realtime playground.
- Manage datasets for **external** training workflows through the CSV Library.

## Deprecated Scope

The old in-app training pipeline under `/training/*` is deprecated and being removed. Train models externally, then upload the exported runtime artifact and metadata into the Playground.

## Runtime Architecture

- `backend` is the API, auth, registry, and dispatch layer.
- `ml-tensorflow` serves TensorFlow-family inference.
- `ml-pytorch` serves PyTorch-family inference.
- `worker-library` reconciles model-library state.
- Runtime model artifacts live in `backend/AI/model_library`.

PyTorch uploads must be callable inference artifacts. `state_dict`-only checkpoints are not valid playground runtime artifacts.

## Quick Start

Requirements:
- Python 3.10+
- Node.js LTS
- npm
- MongoDB

Backend API:

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-api.txt
python3 create_users.py
```

Frontend:

```bash
cd vue-next
npm install
```

Local dev:

```bash
./run_dev.sh
```

Runtime-split Docker profile:

```bash
USE_RUNTIME_SERVICES=true USE_WORKER_LIBRARY=true \
docker compose -f docker-compose.dev.yml --profile runtime-split up -d
```

## Default Dev URLs

- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8000`
- TensorFlow runtime: `http://localhost:8091`
- PyTorch runtime: `http://localhost:8092`
- Worker library: `http://localhost:8093`

## Documentation

- [docs/README.md](docs/README.md)
- [docs/instruction.md](docs/instruction.md)
- [docs/migration_guide.md](docs/migration_guide.md)
- [docs/runtime_service_contract.md](docs/runtime_service_contract.md)

## Notes

- Keep secrets out of version control. Use `backend/.env` for local configuration.
- The backend API container should use `backend/requirements-api.txt`, not the monolithic ML dependency set.
