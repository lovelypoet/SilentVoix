# Temporal Inference Alignment for SilentVoix

This documentation addresses the "Inference Gap" causing low confidence issues. It aligns your Colab training logic with the SilentVoix backend.

## 1. The Root Cause: "The Flattening Mismatch"

Your model was trained on 3D cubes `(1, 60, 63)`. Previously, the backend treated these as flat vectors without proper preprocessing. We have now moved the preprocessing logic to the backend to ensure consistency.

## 2. Updated Model Metadata (metadata.json)

Ensure your metadata includes the `input_spec` for temporal support.

```json
{
  "model_name": "SilentVoix-V2-Temporal",
  "model_family": "lstm",
  "export_format": "pytorch",
  "input_spec": {
    "feature_dim": 63,
    "sequence_length": 60,
    "shape": [1, 60, 63],
    "preprocess_profile": "cv_wrist_center_v1"
  }
}
```

## 3. Frontend Implementation: Raw Sequence Buffering

The Client-Side (Frontend) is now much simpler. It only needs to maintain a raw buffer of landmark frames; the backend handles the math (centering and interpolation).

### A. The Buffer Logic
Maintain a rolling array of landmark frames. As new MediaPipe landmarks arrive, push to the array and shift the oldest out.

### B. Dispatch
Send the entire array (as a `sequence` field) to the `/playground/predict/cv` endpoint.

## 4. Backend Preprocessing (PlaygroundService.py)

The backend now performs the "heavy lifting" to ensure 100% consistency with training:
- **Wrist-Centering**: Automatically subtracts the wrist anchor (landmark 0) for every frame.
- **Linear Interpolation**: Automatically resizes the sequence to match your model's `sequence_length`.

## 5. Summary Checklist for Success

- **Retrain with Copy Fix**: Ensure your training data is preprocessed identically.
- **Frontend Windowing**: Ensure the frontend is sending a sequence of frames in the `sequence` field.
- **Reshape in Adapter**: The `RuntimeAdapter` handles the 3D reshape automatically based on `input_spec`.