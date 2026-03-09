# Plan: Realtime Dual-Model Late Fusion Playground

## Goal
Enable users to perform "Late Fusion" (Decision Fusion) in real-time by running a CV model and a Sensor model simultaneously and merging their predictions using a weighted average—**without requiring extra training.**

## 1. Core Logic: The Fusion Formula
Late fusion will be calculated on the client-side (frontend) to allow for instant slider updates:
`Final Probability(Label) = [CV_Prob(Label) * (1 - W)] + [Sensor_Prob(Label) * W]`
Where `W` is the **Glove Weight** (0.0 to 1.0).

## 2. UI/UX Changes (RealtimeAIPlayground.vue)

### A. Model Selection
- Replace the single "Active Model" selector with a **Fusion Configuration** panel when Fusion Mode is enabled.
- **Slot 1:** Select CV Model (filtered to `modality: "cv"`).
- **Slot 2:** Select Sensor Model (filtered to `modality: "sensor"`).

### B. Fusion Control
- **Sync Slider:** A "Glove vs. Vision" weight slider.
- **Toggle:** "Enable Dual-Model Fusion".

### C. Live Preview
- Enable **both** the Camera Feed and the Sensor Telemetry grid at the same time.
- Show both CV landmarks and real-time glove values.

### D. Prediction Output
- Show the **Fused Result** as the primary prediction.
- Add a "Logic Breakdown" section showing:
  - "Vision says: Hello (90%)"
  - "Glove says: Hello (40%)"
  - "Final (Weighted): Hello (50%)"

## 3. Backend Support
- The current `/model-library/predict/cv` and `/model-library/predict/sensor` endpoints already accept a `model_id` in the request body.
- No new backend endpoints are strictly required, but we must ensure both runtimes (TensorFlow/PyTorch) can handle simultaneous requests.

## 4. Technical Constraints & Validation
- **Label Alignment:** Late fusion only works if both models use the **exact same labels**. The UI should warn the user if the labels don't match.
- **Latency:** Running two models in parallel increases network overhead. We will implement `Promise.all` for the API calls to minimize the delay.
- **Preprocessing:** Ensure `cv_values` and `sensor_values` are formatted correctly for their respective models before sending.

## 5. Implementation Phases

### Phase 1: Frontend State Reform
- Add `activeCvModel` and `activeSensorModel` to the component state.
- Update `loadActiveModel` to handle dual-slot assignment.

### Phase 2: The Fusion Loop
- Create a `predictFusion()` function that triggers when both streams are active.
- Use `Promise.all([predictCv, predictSensor])` to fetch raw probabilities.
- Implement the weighted average logic and label mapping.

### Phase 3: UI Polish
- Create the "Fusion Control" UI group.
- Update the video/telemetry layout to handle "Split View" (Camera + Data).

## 6. Success Criteria
- User can select a CV model and a Sensor model.
- Moving the slider instantly changes the final "Fused" prediction label.
- The system correctly handles a "No Hand Detected" state for CV while still showing Sensor predictions.
