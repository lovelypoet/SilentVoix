# Fusion Preprocessing Worker Plan

## Status

Phase 1 is now implemented.

What exists today:
- dedicated `worker-fusion-preprocess` service
- backend proxy routes under `/fusion-preprocess/*`
- early-fusion cropper integration with worker-backed analysis
- worker validation summary in the cropper
- optional video upload from the cropper for OpenCV motion analysis
- save processed fusion CSV into CSV Library
- CSV Library validation badge sourced from worker sidecar metadata
- CSV Library filtering and sorting by worker validation state
- explicit operator review actions for processed fusion datasets
- operator review notes and review history stored in worker sidecar metadata

Current limitation:
- OpenCV is now used for uploaded capture video motion analysis, but the pipeline still depends on the operator providing the matching video file manually
- preprocessing is still driven by CSV export plus optional video, not by native capture artifacts/job queue ingestion
- persistence is local file storage, not a queued job system with retries/history UI

## Problem

Early-fusion data collection currently depends on browser-side CV capture plus glove sensor capture. This works for a basic prototype, but it breaks down when the user is wearing the glove during camera capture.

The main issue is not only synchronization math. The deeper problem is that the glove changes the visual appearance of the hand enough that browser-side MediaPipe tracking becomes unreliable.

Observed symptoms:
- MediaPipe loses the hand or produces unstable landmarks when the glove is visible.
- Fusion capture becomes difficult for the user even when the sensor stream is healthy.
- Real-time operator workflow becomes too fragile for building a clean training dataset.
- Data quality problems are only discovered late, usually after export.

## Root Cause

The glove creates a CV domain shift:
- fingertips and finger contours may be partially occluded
- glove material changes contrast and silhouette
- reflective or textured surfaces can confuse hand detection
- browser camera pipelines are harder to tune than an OpenCV preprocessing pipeline

This means the current CV capture stack is doing too much in the wrong place:
- browser-side MediaPipe is expected to perform tracking
- the early-fusion pipeline assumes the live CV signal is already good enough
- preprocessing and validation are too light for gloved-hand capture

## Why Sync Math Alone Is Not Enough

The current sync-spike approach is still valid as an alignment method:
- detect a spike in CV
- detect a spike in sensor data
- compute `offset_ms`
- crop to the shared event window
- reject bad samples by threshold

But that only works if the CV side is reliable enough to produce a stable spike signal.

If glove-aware CV preprocessing is weak, then:
- spike detection becomes noisy
- crop boundaries become less trustworthy
- users export bad fusion samples
- validation comes too late

## Decision

Introduce a dedicated preprocessing worker for fusion capture.

This worker should be separate from:
- `backend`
- `ml-tensorflow`
- `ml-pytorch`
- `worker-library`

Suggested service name:
- `worker-fusion-preprocess`

Implementation status:
- done in phase 1

## Why A Separate Worker

Fusion preprocessing should not live in the main backend or inference services.

Reasons:
- OpenCV preprocessing is CPU-heavy and bursty
- preprocessing has different dependencies from inference
- API responsiveness should not depend on CV preprocessing load
- runtime inference services should stay focused on model execution
- preprocessing jobs are easier to monitor and retry when isolated

This follows the same architecture principle already used for runtime split services.

## Scope Of The Worker

The worker is responsible for fusion-only preprocessing and validation.

Primary responsibilities:
- load raw early-fusion capture artifacts
- run OpenCV-based preprocessing for gloved-hand CV
- derive motion/sync candidates from CV
- compute alignment suggestions against sensor data
- propose crop boundaries
- generate validation summary
- export processed fusion dataset plus metadata

Out of scope:
- realtime model inference
- general app camera UI
- model upload/runtime-check
- non-fusion dataset management

Phase 1 implementation scope:
- analyze captured fusion CSV exports
- optionally analyze matching capture video with OpenCV
- apply crop rules
- compute validation summary
- export processed CSV and metadata
- save processed result into CSV Library

## Proposed Processing Flow

1. User captures raw CV + sensor data.
2. Raw capture is stored without destructive preprocessing.
3. User opens cropper/review flow.
4. Backend submits a preprocessing job to `worker-fusion-preprocess`.
5. Worker runs OpenCV preprocessing on the CV stream.
6. Worker computes:
   - motion spike candidates
   - `offset_ms`
   - crop window suggestions
   - sync quality score
   - validation flags
7. Worker writes:
   - processed CSV
   - metadata JSON
   - validation summary
8. CSV Library exposes result as:
   - `valid`
   - `warning`
   - `invalid`

Current implemented flow:
1. User exports `cv_sensor_*.csv` from early-fusion capture.
2. User opens Early Fusion Cropper.
3. Cropper sends CSV + crop rules to `worker-fusion-preprocess`.
4. If the operator provides the matching capture video, the worker runs OpenCV motion analysis on that video.
5. Worker returns:
   - processed CSV text
   - metadata
   - validation summary
   - optional OpenCV video summary
6. User can:
   - download processed CSV
   - download metadata JSON
   - save processed CSV into CSV Library
7. CSV Library shows worker validation status directly in the file list and stats modal.
8. Operator can filter and sort datasets by validation state during review.
9. Operator can mark processed datasets as `approved`, `needs_review`, or `rejected`.
10. Each operator review can include notes, and CSV Library keeps the full review history for audit.

## Why OpenCV Belongs Here

OpenCV should be added only for the fusion path, where glove-aware preprocessing is necessary.

Benefits:
- better contrast and threshold control
- glove-aware segmentation or masking
- more stable motion detection for sync
- better crop estimation
- lower dependence on browser-only MediaPipe behavior

OpenCV should be used first for:
- preprocessing
- motion/sync detection
- crop suggestion
- validation

It does not need to replace all landmark logic immediately.

## Recommended Service Boundaries

### `backend`
- auth
- routing
- dataset orchestration
- preprocessing job creation
- metadata/status retrieval

### `worker-fusion-preprocess`
- OpenCV preprocessing
- sync and crop analysis
- validation and artifact generation

### `ml-tensorflow` / `ml-pytorch`
- inference only

### `worker-library`
- registry reconciliation only

## Job Model

This should be job-based first, not realtime-first.

Recommended job stages:
- `queued`
- `running`
- `completed`
- `failed`

Recommended job outputs:
- processed dataset path
- metadata path
- validation status
- health flags
- numeric summary fields

Current phase 1 job contract:
- `POST /fusion-preprocess/jobs/analyze`
- `POST /fusion-preprocess/jobs/analyze-upload`
- `GET /fusion-preprocess/jobs/{job_id}`
- `POST /fusion-preprocess/jobs/{job_id}/save`

Current save target:
- `backend/data/csv_library/active/fusion_single/*.csv`
- `backend/data/csv_library/active/fusion_dual/*.csv`
- sidecar metadata stored as `*.metadata.json`

Current review metadata:
- `operator_review`
- `review_history[]`
- `review_history_count`

This is safer and easier to debug than trying to add full realtime preprocessing immediately.

## Validation Requirements

The preprocessing worker should produce a clear take-level validation summary.

Minimum fields:
- `cv_spike_detected`
- `sensor_spike_detected`
- `offset_ms`
- `max_abs_sensor_match_delta_ms`
- `missing_frame_ratio`
- `sensor_match_ratio`
- `status` = `pass | warning | reject`
- `reasons[]`

Suggested thresholds:
- pass: `|offset_ms| <= 500`
- warning: `500 < |offset_ms| <= 2000`
- reject: `|offset_ms| > 2000`
- reject when spike detection fails on either side

Current phase 1 validation fields:
- `status`
- `reasons[]`
- `offset_ms`
- `max_abs_sensor_match_delta_ms`
- `sensor_match_ratio`
- `missing_frame_ratio`
- `cv_spike_detected`
- `sensor_spike_detected`
- `opencv_summary` when a matching video is uploaded

## UI / UX Implications

The current UX makes the user do too much manual trust-based work.

The target workflow should be:
- capture raw data
- preprocess
- review validation summary
- crop if needed
- save as processed dataset

The user should not need to guess whether a sample is usable.

The UI should show:
- sync detected or not
- offset quality
- crop range
- data quality flags
- final acceptance state

Implemented UI surfaces:
- Early Fusion Cropper:
  - worker validation card
  - optional capture-video upload
  - OpenCV motion summary panel
  - processed summary
  - save-to-CSV-Library action
- CSV Library:
  - per-file validation badge
  - worker validation details in stats modal
  - validation filter (`pass`, `warning`, `reject`, `unreviewed`)
  - sort controls for newest, oldest, worst validation first, and largest offset first
  - operator review actions:
    - `approve`
    - `needs review`
    - `reject override`
  - operator review badge in the table and stats modal
  - review note dialog before saving operator review
  - review history list in stats modal

## Docker / Deployment Impact

Add one new service in development and runtime deployments:
- `worker-fusion-preprocess`

Likely dependencies:
- `opencv-python`
- `numpy`
- lightweight file/job utilities

This service should mount:
- raw fusion capture directory
- processed dataset output directory
- optional shared CSV library path

Current dev compose status:
- `docker-compose.dev.yml` starts `worker-fusion-preprocess` by default
- backend uses:
  - `USE_FUSION_PREPROCESS_WORKER=true`
  - `FUSION_PREPROCESS_WORKER_URL=http://worker-fusion-preprocess:8094`

## Suggested Next Steps

Completed:
1. Add this worker as a new Docker service.
2. Define a backend job contract for preprocessing requests.
3. Extend the cropper to consume validation output from the worker.
4. Save processed fusion outputs into CSV Library with health flags.
5. Add dataset badges:
   - `pass`
   - `warning`
   - `reject`

Next:
1. Move from manual video upload to native capture artifact ingestion from the capture flow.
2. Expand OpenCV from motion-only analysis to glove-region preprocessing and crop suggestion.
3. Persist richer worker job history and artifact lineage.
4. Add crop/timeline visualization instead of table-only preview.
5. Add stronger validation thresholds for dual-hand/gloved-hand cases.
6. Add review history filtering and reviewer attribution once authenticated operator identity is available in the sidecar.

## Summary

The real problem is not just offset computation. The real problem is that gloved-hand fusion capture needs stronger CV preprocessing than browser MediaPipe can reliably provide.

A dedicated OpenCV-based fusion preprocessing worker is the correct architectural response because it:
- isolates heavy CV work
- improves gloved-hand data quality
- reduces pressure on the backend and runtime services
- creates a proper validation gate before training data is accepted
