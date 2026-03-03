# Technical Specification: Early Fusion Multimodal Pipeline (v1.0)
**Role:** Senior Software Engineer / System Architect
**Project:** SilentVoix Hybrid Recognition
**Methodology:** Feature-Level Concatenation (Early Fusion)

## 1. System Architecture
In an Early Fusion setup, the "Brain" (the Model) expects a single, wide feature vector. Because the Camera and Glove have different sampling rates, we implement a **Time-Window Sync Buffer** on the client-side (Web Browser).



## 2. The Fused Feature Map
The input vector $\vec{X}$ for our model is defined as:
$$\vec{X} = [G_{flex1...5}, G_{imu1...6}, V_{landmark1...21(x,y,z)}]$$

| Modality | Source | Dims | Features |
| :--- | :--- | :--- | :--- |
| **Glove** | ESP32 (Web Serial API) | 11 | 5 Flex + 3 Accel + 3 Gyro |
| **Vision** | MediaPipe (Camera) | 63 | 21 Landmarks * (x, y, z) |
| **Total** | **Fused Vector** | **74** | **Input Layer Size** |

## 3. Web Implementation Strategy

### A. Data Acquisition (The Hooks)
We use the **Web Serial API** for the glove and **MediaPipe Hands** for the vision.

```javascript
// Pseudo-code for Feature Aggregator
let currentGloveFrame = null;
let currentVisionFrame = null;

// Glove Stream (via Web Serial)
port.on('data', (data) => {
    currentGloveFrame = parseGloveData(data); // [f1, f2, f3, f4, f5, ax, ay, az, gx, gy, gz]
});

// Vision Stream (via MediaPipe)
onResults((results) => {
    if (results.multiHandLandmarks) {
        currentVisionFrame = flattenLandmarks(results.multiHandLandmarks[0]); // [x1, y1, z1...z21]
    }
});
```

## 4. System 1 Scope: Vision Dimensionality Policy (Current Decision)

We will support both user-selected capture modes:

- **Single-hand mode:** Vision features = **63 dims** (`21 * (x,y,z)`)
- **Dual-hand mode:** Vision features = **126 dims** (`2 * 21 * (x,y,z)`)

This is valid and future-proof for training both interaction styles, with one strict constraint:

1. Train **single-hand models** only with single-hand (`63`) datasets.
2. Train **dual-hand models** only with dual-hand (`126`) datasets.
3. Persist `mode`/`feature_dim` metadata in dataset and model records.
4. Route inference input to the matching model by mode.

Do **not** mix 63-dim and 126-dim samples in one fixed-input training run.

## 5. System 1 Scope: Sensor Dimensionality Policy (Current Decision)

Sensor features will follow the same mode strategy:

- **Single-hand mode (1 glove):** Sensor features = **11 dims**
  - `[f1, f2, f3, f4, f5, ax, ay, az, gx, gy, gz]`
- **Dual-hand mode (2 gloves):** Sensor features = **22 dims**
  - `left[11] + right[11]`

Therefore expected fused input sizes become:

- **Single-hand fused vector:** `11 (sensor) + 63 (vision) = 74 dims`
- **Dual-hand fused vector:** `22 (sensor) + 126 (vision) = 148 dims`

Training/inference rules mirror Section 4:

1. Single-hand training uses only `74`-dim fused samples.
2. Dual-hand training uses only `148`-dim fused samples.
3. Persist `mode`, `sensor_dim`, `vision_dim`, and `fused_dim` in dataset/model metadata.
4. Never mix `74` and `148` samples in one fixed-input model run.

## 6. Implementation Plan For Training UI

### A. Should it be one page or two pages?

**Recommendation:** Use **two separate pages**:

- `Late Fusion Training`
- `Early (Feature) Fusion Training`

Reason:

1. Different dataset schemas (`late` keeps modality outputs separate, `early` needs strict fused dims).
2. Different validation rules and model contracts.
3. Lower risk of operator mistakes (wrong mode/model pairing).

You can still reuse shared UI components (camera panel, sensor status, log terminal, export button styles).

### B. Page responsibilities

#### 1) Late Fusion Training Page

- Keep current late-fusion workflow.
- Output separate modality-aligned artifacts (or late-fusion compatible export).
- Train/evaluate late-fusion models only.

#### 2) Early Fusion Training Page

- Force explicit mode selection: `single` or `dual`.
- Build fixed fused vectors:
  - single: `74` dims
  - dual: `148` dims
- Block export if row dims do not match selected mode.
- Save metadata with every export:
  - `fusion_type=early`, `mode`, `sensor_dim`, `vision_dim`, `fused_dim`, `schema_version`.

### C. Backend/API additions for Early Fusion page

1. `POST /fusion/early/export` (admin-only): persist fused dataset file + metadata.
2. `GET /fusion/early/datasets` (admin-only): list datasets and schema dims.
3. `POST /fusion/early/train` (admin-only): train with selected dataset and mode.
4. `GET /fusion/early/models` (admin-only): list trained early-fusion models with input dims.

### D. Safety gates (must-have)

1. Reject training if mixed dims are detected in a dataset.
2. Reject inference if runtime vector dim != model input dim.
3. Show hard warning in UI when model mode and capture mode differ.

### E. Delivery order (one problem at a time)

1. Add the second page route + skeleton (`Early Fusion Training`).
2. Implement strict fused-row builder (`74`/`148`) and export validator.
3. Add backend dataset persistence endpoints (admin-only).
4. Add early-fusion training endpoint with dim checks.
