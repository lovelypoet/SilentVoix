## YOLO + LSTM Runtime Fix Plan

### Goal

Make the integrated **YOLO detector + LSTM classifier** path in Realtime AI Playground:

- actually load the LSTM,
- return real gesture predictions (not just landmarks / "Waiting..."),
- and keep behavior consistent with the standalone training pipeline.

---

### 1. Current State (Quick Facts)

- **Detector (YOLO)**:
  - We use Ultralytics YOLO from `backend/AI/models/best.pt` or a `yolo` model from the model library registry.
  - Metadata file: `backend/AI/models/metadatayolo.json` (used when uploading YOLO into the registry).

- **Classifier (LSTM)**:
  - Trained in `backend/AI/models/yolo.py` (`HandLSTMClassifier`).
  - Checkpoint saved as a **state_dict** (`torch.save(model.state_dict(), ...)`), not a full TorchScript model.
  - Live integrated service (`GestureService`) tries to load `best_model 2.pth` via `runtime_adapter.load_runtime(..., is_state_dict=True, has_model_class=True)`.
  - There is **no `model.py` file** next to the checkpoint, so state_dict loading via runtime adapter fails.

- **Integrated runtime endpoint**:
  - Path: `/predict/integrated`
  - Backend: `GestureService.predict_frame` in `backend/services/gesture_service.py`
  - Frontend: Realtime AI Playground when toggled to **"YOLO+LSTM (Server)"**.

---

### 2. Problems

1. **LSTM never loads in GestureService**
   - Hard-coded path: `best_model 2.pth` (with a space) in `AI/models/`.
   - Actual file present in repo: `backend/AI/models/best_model2.pth` (no space).
   - `load_runtime(..., is_state_dict=True, has_model_class=True)` expects a `model.py` defining an `nn.Module` class, but that file does not exist.
   - Result: exception in `__init__`, `self.lstm_runtime` stays `None`.

2. **Integrated path returns only landmarks**
   - `predict_frame` only classifies when:
     - `len(self.frame_buffer) == self.sequence_length`, **and**
     - `self.lstm_runtime is not None`.
   - Because `self.lstm_runtime` is `None`, it always falls through to:
     - `gesture: "Waiting..."`, `confidence: 0.0`, plus landmarks.

3. **LSTM-only (playground classifier) always predicts "Goodbye" ~90%**
   - The generic `/model-library/predict/cv` path uses:
     - `metadata.labels` for label names and order.
     - `metadata.input_spec.sequence_length` / `feature_dim` to shape inputs.
   - If labels order or input_spec do not match how the LSTM was trained, predictions become biased / mis-mapped.

---

### 3. Target Design

We want:

- **A single source of truth for the LSTM architecture and labels**, shared between training and runtime.
- Integrated service that:
  - Loads YOLO from either `best.pt` or a registry model.
  - Loads LSTM from `best_model2.pth` (or similar) plus its Python class.
  - Uses `metadata6.json` (or equivalent) to set:
    - `input_spec.sequence_length`
    - `input_spec.feature_dim`
    - `labels` (correct order)
  - Returns predictions as `{ gesture, confidence, landmarks, buffer_status }`.

---

### 4. Implementation Steps

#### Step 1 – Add a runtime `model.py` for the LSTM

- Create `backend/AI/models/model.py` containing:
  - `HandLSTMClassifier` copied from `backend/AI/models/yolo.py` (training script).
  - Only the class definition and any tiny utilities strictly required to construct it.
- This file will be used by `runtime_adapter.load_runtime(..., is_state_dict=True, has_model_class=True)` to reconstruct the `nn.Module` and load the state_dict.

#### Step 2 – Fix the checkpoint path

- In `backend/services/gesture_service.py`:
  - Change `lstm_path = os.path.join(base_ai_dir, "best_model 2.pth")`
  - To match the actual filename, e.g.:
    - either rename the file on disk to `best_model 2.pth`, or
    - change the code to `best_model2.pth` (no space).
- Keep `is_state_dict=True` so runtime adapter knows it is a state_dict, not a full model file.

#### Step 3 – Confirm metadata for integrated LSTM

- In `backend/AI/models/metadata6.json` (or the metadata file you want to use for integrated LSTM), ensure:
  - `input_spec.sequence_length` = the sequence length used in training (`params['seq_length']`, currently 16 in `yolo.py`).
  - `input_spec.feature_dim` = `63`.
  - `labels` = the same list and order as `params['classes']` in `yolo.py`.
- GestureService already reads this file and sets:
  - `self.sequence_length`
  - `self.feature_dim`
  - `self.labels`

#### Step 4 – Smoke test integrated endpoint

- With backend running:
  - POST a single image frame to `/predict/integrated` (the playground does this via the "YOLO+LSTM (Server)" toggle).
  - Observe:
    - `gesture` should change from `"Waiting..."` to a real label after enough frames fill the buffer (`sequence_length`).
    - `buffer_status` should show `N/sequence_length` and eventually stay at `sequence_length/sequence_length`.

#### Step 5 – Re-evaluate LSTM-only path in playground

- Once integrated path works and labels/sequence settings are correct, revisit the generic CV runtime path:
  - Ensure the `metadata.json` that you upload with the exported LSTM model:
    - Uses the same `labels` and `input_spec` as above.
  - Verify that `/model-library/predict/cv` now returns a sensible distribution instead of always "Goodbye".

---

### 5. Next Actions (What we’ll actually change in code)

1. **Create `backend/AI/models/model.py` with `HandLSTMClassifier`**.
2. **Update `GestureService` to point to the correct LSTM checkpoint filename**.
3. **Verify / adjust `metadata6.json` to match training config**.
4. **Run quick manual tests against `/predict/integrated` and the Realtime AI Playground YOLO+LSTM mode**.

We can iterate on this document as we make changes (e.g. add troubleshooting notes for common errors: missing model.py, dimension mismatch, bad labels ordering).

