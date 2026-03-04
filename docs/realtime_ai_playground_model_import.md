# Realtime AI Playground: Plug-in Model Import Spec (v1)

## Objective
Allow admin/editor users to upload an **already exported model** (within supported model families such as LSTM to CNN), then run real-time camera inference with bounding boxes and predictions.

## Core Flow
1. User opens **Realtime AI Playground**.
2. User uploads model artifact package (exported format only).
3. System reads model metadata (including model name/family/input shape/labels).
4. System validates compatibility with CV pipeline.
5. User starts camera stream.
6. System draws hand bounding boxes + live predicted label/confidence.

## Supported Model Families (initial range)
- LSTM-based sequence models (exported for inference)
- CNN-based image/frame models (exported for inference)
- Other deep learning models within the curated acceptance range: `.tflite`, `.keras`, `.h5`, `.pth`
- Optional extension: hybrid CNN+LSTM exported variants

Note: training framework is not required at runtime; only the exported inference artifact is loaded. Support for `onnx` is a separate future milestone.

## Required Upload Contract
Package must include:
- model artifact file (runtime-loadable)
- metadata file (JSON), minimum fields:
  - `model_name`
  - `model_family` (`lstm`, `cnn`, `cnn_lstm`, etc.)
  - `input_spec` (shape, expected preprocessing)
  - `labels` (ordered class list)
  - evaluation metrics summary: `precision`, `recall`, `f1` (macro or weighted, with metric type specified)
  - `export_format` and `version`

If metadata is missing or invalid, upload is rejected.

## Runtime Validation Rules
- Exported format must be in allowed runtime formats.
- `model_family` must be in allowed family range.
- `input_spec` must match supported CV preprocessor mode.
- `labels` must be non-empty and deterministic order.
- Model filename and metadata `model_name` should be logged; metadata value is authoritative.

## UI Behavior
- Upload panel:
  - drag/drop or file picker
  - validation status + error reasons
  - loaded model summary (`model_name`, family, input)
- Live panel:
  - camera preview
  - hand bounding boxes
  - predicted label + confidence
  - top-k probabilities
  - model quality summary panel: precision / recall / F1 (from uploaded metadata)
  - FPS and inference latency

## Backend/Service Responsibilities
- Parse metadata safely.
- Cache loaded model by `model_name + version`.
- Provide inference endpoint/session for live frames.
- Return structured prediction payload:
  - bounding box
  - label
  - confidence
  - class probabilities
  - model metadata used
  - model evaluation summary (`precision`, `recall`, `f1`) for UI display/audit context

## Security and Role Scope
- Upload/replace model: admin/editor only.
- Run live inference: editor/viewer (configurable).
- Maintain audit log: uploader, timestamp, model name/version, checksum.

## Acceptance Criteria
- User can upload supported exported model package successfully.
- Playground displays parsed model name/family.
- Playground displays uploaded model quality metrics (precision, recall, F1).
- Live camera inference runs using uploaded model.
- Bounding boxes and prediction labels are visible in real time.
- Invalid format/metadata fails with clear error message.
