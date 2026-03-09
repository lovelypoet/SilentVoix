# Blueprint: Time-Series Dataset Aligner (SilentVoix "Surgeon")

## Goal
Transform the "Late Fusion Training" page into a professional **Dataset Alignment & Synchronization Tool**. This tool allows researchers to visually sync Computer Vision (CV) landmarks and Glove (Sensor) data, nudging them to fix hardware latency and trimming "dead air" before exporting "Golden Data" for training.

## 1. The "Visual Editor" Architecture
### A. The Timeline (Multi-Track)
- **Track 1 (Reference):** CV Landmark Waveform (e.g., `Wrist_Y`).
- **Track 2 (Alignment):** Sensor Channel Waveform (e.g., `Flex_Index`).
- **Playhead:** A vertical line that follows the mouse/scrubbing.
- **Video Window:** A synced video player that jumps to the frame corresponding to the playhead.

### B. Transformation Controls
- **Global Nudge (Offset):** A slider to shift the entire Sensor track forward/backward (ms).
- **Trim Handles:** Draggable "In" and "Out" markers to crop the start/end of the session.
- **Auto-Sync Button:** (Optional Phase 2) Uses Cross-Correlation to guess the best offset.

## 2. Technical Strategy
### A. Data Fetching
- Create a high-speed backend endpoint to stream raw CSV rows.
- Use **Downsampling** on the frontend: If a file has 5,000 rows, we render every 5th or 10th point to keep the Canvas 60FPS.

### B. The Canvas Engine
- Use a lightweight, custom HTML5 Canvas renderer for the waveforms.
- Draw two parallel graphs with a shared X-axis (Time).
- Support **Zooming** and **Panning** to find fine-grained alignment issues.

### C. The Fusion Math (Linear Interpolation)
- Since camera and sensors have different frequencies (30Hz vs 100Hz), the alignment tool will:
  1. Set a "Master Clock" (usually the CV timestamps).
  2. For every CV timestamp, find the two closest Sensor points.
  3. Perform **Linear Interpolation** to calculate the sensor values at the exact CV frame time.

## 3. Workflow Pivot
1. **Select Pair:** Pick a CV CSV and a Sensor CSV from the CSV Library.
2. **Visualize:** Review the waveforms. Find a "High Motion" moment (a hand snap or closure).
3. **Align:** Nudge the sensor track until the spikes line up with the CV landmarks.
4. **Trim:** Crop the beginning/end.
5. **Export:** Generate the final "Fused" CSV (74/148 dims).

## 4. Implementation Steps

### Phase 1: Structure & Routing
- Rename `LateFusionTraining.vue` $\rightarrow$ `DatasetAligner.vue`.
- Update Sidebar/Router to "Dataset Aligner".
- Implement `GET /admin/csv-library/files/{name}/full-data` on the backend.

### Phase 2: The Waveform Canvas
- Implement the "Dual-Track" canvas component.
- Basic "Nudge" slider that shifts the rendered data.

### Phase 3: The "Surgeon" Export
- Implement the Interpolation + Trimming logic.
- Create the final "Fusion Export" endpoint.

## 5. Success Criteria
- User can visually identify a 50ms drift between video and glove.
- User can fix the drift with a slider and see the graphs "click" into alignment.
- The exported CSV has zero "dead air" and perfectly synchronized time-series.
