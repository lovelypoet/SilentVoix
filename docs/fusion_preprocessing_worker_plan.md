# Fusion Preprocessing Worker Plan

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

## Suggested Next Steps

1. Add this worker as a new Docker service.
2. Define a backend job contract for preprocessing requests.
3. Extend the cropper to consume validation output from the worker.
4. Save processed fusion outputs into CSV Library with health flags.
5. Add dataset badges:
   - `valid`
   - `warning`
   - `invalid`

## Summary

The real problem is not just offset computation. The real problem is that gloved-hand fusion capture needs stronger CV preprocessing than browser MediaPipe can reliably provide.

A dedicated OpenCV-based fusion preprocessing worker is the correct architectural response because it:
- isolates heavy CV work
- improves gloved-hand data quality
- reduces pressure on the backend and runtime services
- creates a proper validation gate before training data is accepted
