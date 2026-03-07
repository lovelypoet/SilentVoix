# AI Runtime Improvement (CV Focus)

## Problem Summary
Low confidence in live CV inference usually means runtime preprocessing does not match training preprocessing.

If the model was trained with:
- wrist-centered landmarks, and
- fixed-length temporal sequences (for example 60 frames),

then sending raw single-frame vectors will degrade accuracy.

## Critical Rule
Runtime must replicate the exact training transform pipeline.

For sequence CV models, that means:
1. Build consistent per-frame landmark vectors.
2. Apply the same coordinate normalization (for example wrist-centering).
3. Build a fixed sequence length using real interpolation (not index sampling).
4. Feed the tensor shape expected by the exported model.

## Correct Preprocessing Spec (Example: 60 x 63)

Assume each frame is 63 features (`21 landmarks * (x,y,z)`).

### 1) Wrist-Centering
For each frame, subtract landmark 0 `(x0,y0,z0)` from every landmark.

Important:
- Copy the anchor first, then subtract.
- Do not mutate `data[:, 0:3]` before using it as the anchor for the rest of the landmarks.

### 2) Temporal Resize to Target Frames
Use linear interpolation over time for each feature dimension.

Do not use `np.linspace(...).astype(int)` indexing when you need interpolation; that is re-sampling, not interpolation.

### 3) Tensor Shape
For an LSTM-like model:
- input shape should typically be `(batch, timesteps, features)`, e.g. `(1, 60, 63)`.

## Reference Python Function (Corrected)

```python
import numpy as np
import torch

def prepare_sequence_for_inference(frame_buffer, target_frames=60):
    """
    frame_buffer: list/array with shape (N, 63), N >= 1
    returns: torch.Tensor with shape (1, target_frames, 63)
    """
    data = np.asarray(frame_buffer, dtype=np.float32)
    if data.ndim != 2 or data.shape[1] != 63:
        raise ValueError(f"Expected (N, 63), got {data.shape}")
    if data.shape[0] < 1:
        raise ValueError("Empty frame buffer")

    # 1) Wrist-centering
    anchor = data[:, 0:3].copy()  # preserve original wrist coords
    for i in range(21):
        start = i * 3
        end = start + 3
        data[:, start:end] = data[:, start:end] - anchor

    # 2) Linear temporal interpolation to target_frames
    current_frames = data.shape[0]
    if current_frames != target_frames:
        old_t = np.linspace(0.0, 1.0, current_frames)
        new_t = np.linspace(0.0, 1.0, target_frames)
        interp = np.empty((target_frames, data.shape[1]), dtype=np.float32)
        for feat_idx in range(data.shape[1]):
            interp[:, feat_idx] = np.interp(new_t, old_t, data[:, feat_idx])
        data = interp

    # 3) Tensor shape: (1, T, F)
    return torch.from_numpy(data).unsqueeze(0)
```

## Current SilentVoix Gap
Current Playground CV path uses flat vectors and single-step inference flow.
That is fine for MLP-style/frame models, but not sufficient for temporal sequence models unless runtime is extended.

## Implementation Plan (SilentVoix)

### Phase 1: Preprocess Contract
- Add metadata fields in `input_spec`:
  - `sequence_length` (e.g. 60)
  - `feature_dim` (63 or 126)
  - `preprocess_profile` (e.g. `cv_wrist_center_v1`)

### Phase 2: Playground CV Frontend
- Maintain rolling frame buffer for CV model.
- Apply deterministic hand mapping and preprocessing profile.
- Build sequence payload when model expects sequence input.

### Phase 3: Runtime/Backend Support
- Extend predict contract to accept sequence input for CV models.
- Validate expected shape from metadata before inference.
- Keep backward compatibility for flat vector models.

### Phase 4: Validation
- Add runtime smoke tests for:
  - flat CV model,
  - sequence CV model (60x63),
  - shape mismatch rejection.

## Hardware Notes
For landmark-based sequence inference, CPU is usually enough.

Recommended baseline:
- CPU: modern 4+ core
- RAM: 8-16 GB
- Webcam: stable 30 FPS (60 FPS helps temporal smoothness)

