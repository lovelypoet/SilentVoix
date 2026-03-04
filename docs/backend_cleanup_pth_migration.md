# Backend Cleanup + Scope Migration: Training Platform -> `.pth` Testing Ground

## Goal
- Change product scope to a model testing ground (no in-app training pipeline).
- Remove or isolate legacy TensorFlow/TFLite training paths.
- Prepare a clean backend runtime for PyTorch `.pth` model upload, storage, activation, and inference.
- Keep inference API behavior stable during migration.

## Product Scope Decision
- New scope:
  - Upload exported model packages.
  - Store and activate model versions.
  - Run realtime/batch inference in playground.
  - Show metadata metrics provided by model package (`precision`, `recall`, `f1`).
- Explicitly out of scope:
  - Training models inside this project.
  - Dataset orchestration/pipeline feeding for training.
  - Training visualizations tied to in-app model fitting.

## Scope
- In scope:
  - `backend/AI/train_dual_hand_model.py` (deprecation/removal)
  - `backend/AI/gesture_model_inference.py` (deprecation/removal)
  - `backend/core/model.py` and runtime selection for `.pth`
  - `backend/routes/playground_routes.py` runtime extension to support `.pth`
  - `backend/routes/training_routes.py` deprecation/removal
  - backend dependency cleanup (`requirements*.txt`, Docker image setup)
  - docs rewrite to reflect testing-ground product
- Out of scope:
  - new training features
  - model quality tuning beyond inference smoke tests

## Current Legacy Surface (Observed)
- TensorFlow training script writes `.tflite` artifacts (`train_dual_hand_model.py`).
- Inference script initializes `tf.lite.Interpreter` (`gesture_model_inference.py`).
- Training routes are still active (`/training/run`, `/training/trigger`, dual-hand, late-fusion).
- Playground currently accepts `.tflite`, `.keras`, `.h5` only; no `.pth` runtime yet.

## Deprecation Matrix (Scope Change)
- Remove/deprecate backend training API surface:
  - `POST /training/run`
  - `POST /training/trigger`
  - `POST /training/dual-hand/run`
  - `POST /training/dual-hand/trigger`
  - `POST /training/late-fusion/run`
  - training metrics/visualization endpoints under `/training/*`
- Keep and prioritize testing-ground endpoints:
  - `POST /playground/models/upload`
  - `GET /playground/models`
  - `POST /playground/models/{model_id}/activate`
  - `POST /playground/predict/cv`

## Migration Strategy

### Phase 1: Freeze Legacy Training Features
- Mark training routes as deprecated in docs and route descriptions.
- Add `TRAINING_FEATURES_ENABLED=false` guard to block new training runs immediately.
- Add a feature flag, e.g. `ML_RUNTIME=tflite|torch` (default `tflite` for first rollout).
- Route all model-load calls through one runtime selector module.
- Keep legacy inference reachable only behind explicit flag during transition.

Acceptance criteria:
- Training run endpoints are blocked or clearly marked deprecated.
- App boots with either inference runtime value during transition.
- No direct TensorFlow imports outside the legacy adapter.

### Phase 2: Introduce Torch Runtime
- Add a new inference module (example: `backend/AI/torch_inference.py`) that:
  - loads `.pth` model with `torch.load(..., map_location=device)`
  - sets `model.eval()`
  - performs deterministic preprocessing and output decoding
- Extend playground upload validation to accept `.pth` + matching metadata `export_format`.
- Mirror existing playground prediction response contract so frontend is unchanged.

Acceptance criteria:
- `.pth` model uploads, stores, activates, and loads in container.
- One end-to-end prediction returns valid label and confidence payload.

### Phase 3: Dependency and Container Cleanup
- Update backend dependencies:
  - remove TensorFlow packages (after torch path is validated)
  - add `torch` (CPU/GPU variant depending on deployment)
- Update `backend/Dockerfile` for torch-compatible base/runtime libs.
- Rebuild and verify container startup time and memory usage.

Acceptance criteria:
- `docker compose -f docker-compose.dev.yml up backend` runs cleanly.
- No TensorFlow import errors and no unresolved torch libs.

### Phase 4: Remove Training Surface
- Remove training endpoints and their service wiring from runtime.
- Archive legacy scripts in a dedicated `backend/AI/legacy/` folder before deletion.
- Remove legacy training UI references from docs and navigation (if present).
- Update `core/settings` model path variables to testing-ground inference artifacts.

Acceptance criteria:
- No dead imports to removed modules.
- API/docs reflect testing-ground capabilities only.

### Phase 5: Final Removal
- Delete legacy TFLite-only and training-only code/artifacts after one stable release window.
- Remove legacy feature flag branch if no rollback is needed.

Acceptance criteria:
- Codebase has one active inference runtime path for playground use.
- No executable training pipeline remains in active backend.
- CI/test suite passes with torch-only dependencies.

## Recommended Task Order
1. Freeze/deprecate training features behind `TRAINING_FEATURES_ENABLED=false`.
2. Create runtime selector + `ML_RUNTIME` flag.
3. Land `.pth` loader/inference in playground flow.
4. Add smoke tests for upload/activate/predict/store.
5. Switch default runtime to `torch` and remove TensorFlow deps.
6. Remove training endpoints and legacy training code.

## Suggested Next Actions (Before Coding Features)
1. Announce scope change first in `README` and docs index.
2. Freeze training features, then migrate playground runtime to `.pth`.
3. Validate `.pth` upload/store/predict in Docker before any new feature work.

Why this helps:
- prevents feature rework from backend runtime churn
- keeps fallback available during early migration
- catches environment/runtime issues early (dependencies, model loading, container config)

## Risks and Controls
- Risk: API payload drift during runtime migration.
  - Control: contract tests on prediction response schema.
- Risk: hidden dependencies on old training endpoints.
  - Control: add temporary access logs and remove endpoints in staged PRs.
- Risk: container bloat or startup regressions.
  - Control: measure image size/startup before and after.
- Risk: accidental hard deletion of fallback path too early.
  - Control: archive legacy files and keep one-release rollback window.

## Security/Config Follow-up
- Move plaintext secrets out of `docker-compose.dev.yml` into `.env` immediately.
- Rotate exposed DB credentials if already committed/shared.

## Testing Procedure
1. Pre-check configuration
   - Set `ML_RUNTIME=tflite`, then `ML_RUNTIME=torch` in `.env` (one at a time).
   - Confirm model/env vars point to valid artifacts (`.tflite` for legacy, `.pth` for torch path).
   - Expected result: backend has all required env vars and valid model file paths.

2. Build and start backend in Docker
   - Run: `docker compose -f docker-compose.dev.yml build backend`
   - Run: `docker compose -f docker-compose.dev.yml up -d backend`
   - Check logs: `docker compose -f docker-compose.dev.yml logs -f backend`
   - Expected result: service starts without import/runtime errors.

3. Health check
   - Run: `curl -sS http://localhost:8000/health` (or your active health endpoint).
   - Expected result: HTTP `200` and healthy status payload.

4. Runtime selector validation
   - With `ML_RUNTIME=tflite`, call one prediction endpoint.
   - With `ML_RUNTIME=torch`, call the same endpoint using identical input.
   - Expected result: both paths return the same response schema (label/confidence keys unchanged).

5. Playground upload/store/activate test
   - Upload exported model + metadata.
   - Verify model appears in `GET /playground/models`.
   - Activate it and verify `GET /playground/models/active`.
   - Expected result: model is persisted and active model pointer updates correctly.

6. Torch model smoke test
   - Use a known-good sample input payload for one gesture class through `/playground/predict/cv`.
   - Call prediction endpoint 3-5 times.
   - Expected result: stable, non-error responses and consistent top prediction class for deterministic input.

7. Contract test for API response
   - Validate required fields and types (for example: `label: string`, `confidence: number`).
   - Expected result: no schema drift between runtimes.

8. Training endpoint deprecation/removal test
   - Call deprecated `/training/*` endpoints.
   - Expected result: disabled/deprecated response (during freeze) or 404 (after removal).

9. Regression checks after dependency cleanup
   - Remove TensorFlow deps only after torch path passes.
   - Rebuild backend image and repeat steps 2-8.
   - Expected result: backend still boots and playground predicts with torch-only environment.

10. Failure and rollback rule
   - If torch runtime fails to load model or breaks response contract, switch `ML_RUNTIME=tflite` immediately.
   - Open a fix task with failing request payload + logs attached.

Pass criteria:
- All steps above succeed with `ML_RUNTIME=torch`.
- No TensorFlow import dependency remains in active runtime.
- Playground prediction contract remains backward compatible.
- Training endpoints are no longer active in production runtime.

## Definition of Done
- Backend runs with `.pth` runtime as default.
- Playground upload/store/activate/predict endpoints pass smoke and contract tests.
- TensorFlow/TFLite and training-only dependencies/code are removed.
- `/training/*` backend functionality is disabled or removed per phase plan.
- README/docs are updated to “testing ground” scope only.
