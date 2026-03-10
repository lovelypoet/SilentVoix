# YOLO → Crop → MediaPipe → Sequence → LSTM (Realtime) Implementation Plan

## Goal
Implement the integrated realtime pipeline described in `docs/yololstm.md`:
`Camera frame → YOLO bbox → crop → MediaPipe Hands → preprocess → buffer → LSTM → label`

This should replace the current integrated path (`/predict/integrated`) which uses YOLO keypoints directly.

## Scope
- Realtime only (playground integrated mode).
- Keep existing CV playground mode (browser MediaPipe) unchanged.
- Add backend MediaPipe dependency and a shared pipeline module.

## Current State (Gap)
- `backend/services/gesture_service.py` uses YOLO keypoints directly.
- No MediaPipe is used in the integrated backend path.
- Integrated endpoint: `POST /predict/integrated`.

## Implementation Steps

1. **Add a backend pipeline module**
   - New file: `backend/AI/pipelines/yolo_mediapipe_lstm.py`
   - Responsibilities:
     - `detect_hand_bbox(frame)` using YOLO.
     - `crop_roi(frame, bbox)` with bounds checks.
     - `run_mediapipe(crop)` and return landmarks.
     - `preprocess_landmarks(landmarks)` (wrist-centered, 63-dim).
     - Maintain sequence buffer, run LSTM when full.

2. **Backend MediaPipe setup**
   - Add dependency: `mediapipe` in backend requirements.
   - Initialize MediaPipe Hands once per service instance.
   - Configure:
     - `static_image_mode=False`
     - `max_num_hands=1`
     - `min_detection_confidence=0.5`
     - `min_tracking_confidence=0.5`

3. **Update GestureService**
   - Replace YOLO-keypoint path with:
     - `YOLO bbox → crop → MediaPipe → preprocess`.
   - Keep buffer logic and LSTM runtime prediction.
   - Preserve `buffer_status`, `gesture`, `confidence`, `landmarks`.
   - Ensure `landmarks` is returned in a UI-friendly format (list of 21 points).

4. **Runtime metadata alignment**
   - Ensure `metadata6.json` has:
     - `input_spec.sequence_length = 16`
     - `input_spec.feature_dim = 63`
     - `labels` order matches training.
   - Keep `preprocess_profile` consistent with training (wrist-centered).

5. **Playground integrated UI**
   - No UI change needed.
   - It already calls `/predict/integrated`.
   - We continue returning the same payload fields.

6. **Add a minimal smoke test**
   - Extend `backend/tests/test_integrated_v2.py` or add a small script:
     - Load a single frame or small video.
     - Send to `/predict/integrated`.
     - Verify `status=success`, `gesture` not error, and `buffer_status` increments.

## Data Flow (Realtime)
1. Browser captures frame.
2. `/predict/integrated` receives base64 image.
3. Backend:
   - YOLO detects bbox.
   - Crop ROI.
   - MediaPipe Hands on ROI.
   - Preprocess to 63-dim.
   - Append to buffer.
   - If buffer full → LSTM → label/confidence.
4. Response:
   - `gesture`, `confidence`, `buffer_status`, `landmarks`.
5. UI renders label + skeleton.

## Risks / Notes
- MediaPipe on backend adds CPU/GPU load.
- If YOLO bbox is unstable, MediaPipe detection will flicker.
- Crop bounds must be clamped to frame size.
- If no hand detected, fill zeros to keep buffer length stable.

## Acceptance Criteria
- Integrated mode shows non-`Waiting...` labels after buffer fills.
- Label stability comparable or better than current YOLO-keypoint path.
- Landmarks drawn in UI are aligned with hand position.

