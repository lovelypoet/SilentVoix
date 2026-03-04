# Technical Specification: Early Fusion Multimodal Pipeline (v1.0)

> **⚠️ DEPRECATION NOTICE (March 2026)**
> The in-app training pipeline for Early Fusion (described in Section 6) is now **deprecated**. 
> Users should perform feature-level concatenation and training externally, then use the **Playground Model Upload** feature to import the resulting models.
> See the [Migration Guide](migration_guide.md) for more details.

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

## 7. Data Controller = CSV Library (Recommended)

Yes, the **CSV Library admin page** should be the first version of the **Data Controller page**.

Use the CSV Library as the control surface for:

1. Classifying dataset type.
2. Validating schema compatibility before training.
3. Sorting/filtering files by modality and hand mode.
4. Preventing wrong dataset selection in training pipelines.

Reference implementation note:
- Existing planning doc: `csv_library_admin_plan.md`

## 8. Canonical Dataset Types (6 Schemas)

We define dataset type as:
- `modality` in `{cv, sensor, fusion}`
- `hand_mode` in `{single, dual}`

This yields exactly 6 canonical types:

1. `cv_single`
2. `cv_dual`
3. `sensor_single`
4. `sensor_dual`
5. `fusion_single`
6. `fusion_dual`

## 9. Schema Registry (Type-First Storage)

Every CSV tracked by Data Controller must carry these metadata fields:

- `schema_id` (one of the 6 canonical types)
- `schema_version` (example: `v1`)
- `modality` (`cv` | `sensor` | `fusion`)
- `hand_mode` (`single` | `dual`)
- `feature_dim` (expected model input feature count)
- `label_column` (default: `label`)
- `timestamp_column` (default: `timestamp_ms`)

### Expected feature dims by type

- `cv_single`: `63`
- `cv_dual`: `126`
- `sensor_single`: `11`
- `sensor_dual`: `22`
- `fusion_single`: `74` (`11 + 63`)
- `fusion_dual`: `148` (`22 + 126`)

## 10. Sorting and Filtering Strategy

In CSV Library/Data Controller UI, add top-level filters:

1. `schema_id` (primary filter)
2. `modality`
3. `hand_mode`
4. `schema_version`
5. `label contains`
6. `date range`
7. `health_flags`

Default table sort:

1. `schema_id`
2. `modified_at desc`

Training picker rule:

- Early-fusion training page may only list:
  - `fusion_single` for single mode
  - `fusion_dual` for dual mode
- Late-fusion flows may list compatible modality-separated datasets by design.

## 11. Storage Convention (Simple + Scalable)

Use filename and metadata together (metadata is source of truth):

- Filename pattern:
  - `{schema_id}__{label_group}__{yyyymmdd_hhmmss}__{schema_version}.csv`
- Example:
  - `fusion_single__greetings__20260303_143020__v1.csv`

Suggested directory shape:

- `backend/data/csv_library/active/{schema_id}/...`
- `backend/data/csv_library/archive/{schema_id}/...`

This keeps the 6 types physically separated while preserving searchability.
