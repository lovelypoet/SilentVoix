# Plan: Reforming Gesture Library to "Gesture Insights"

## Goal
Transform the "Gesture Library" from a legacy MongoDB-driven list into a high-level **Visual Data Controller** for the CSV Library. This page will serve as the "Human-Readable" dashboard for your training datasets and real-world model performance.

## 1. Architectural Pivot
- **Old Source:** `sensor_collection` (MongoDB) - *Status: Deprecated for CV Pipeline*
- **New Source:** `admin/csv-library/files` (Filesystem/Metadata) - *Status: Active Data Source*
- **Joining Logic:** Aggregate all CSV files in the `active` directory by their `label` (from metadata) to show total sample counts and health across the entire dataset.

## 2. Renaming & Branding
- **UI Label:** "Gesture Insights"
- **Route:** `/gesture-insights`
- **Component:** `GestureInsights.vue` (renamed from `Library.vue`)
- **Purpose:** "Analyze dataset readiness and real-world model reliability."

## 3. Core Features (The "Insight" Layer)
### A. Dataset Aggregation
- **Samples per Label:** Total rows across all CSVs for a specific sign (e.g., "Hello").
- **Quality Score:** Average health flags from the CSV Library (lighting, stability, etc.).
- **Modality Mix:** Indicator if a gesture has CV, Sensor, or Fusion data available.

### B. Performance Tracking (Existing + Improved)
- **Validation Accuracy:** Pulled from the active model's metadata.
- **Live Reliability:** Pulled from the `feedback_collection` (user corrections in Playground).
- **Reliability Index:** Color-coded progress bar (Green/Yellow/Red).

### C. Actionable Recommendations
- **"Low Data":** If samples < 1000.
- **"Struggling":** If Reliability < 70% despite high data volume (indicates bad data quality).
- **"Ready":** High reliability and sufficient data.

## 4. Implementation Steps

### Phase 1: Backend (The Insight Engine)
- Update `backend/routes/admin_csv_library_routes.py` to include an `/insights` endpoint.
- This endpoint will:
  1. Scan all `active` CSV files.
  2. Aggregate counts by label.
  3. Join with `feedback_collection` for the active model.
  4. Return a "Unified Gesture Identity" object.

### Phase 2: Frontend (The Visual Skin)
- Rename `Library.vue` -> `GestureInsights.vue`.
- Update `App.vue` and `router/index.js` navigation labels.
- Update `api.js` to call the new insights endpoint.
- Refactor the "Gesture Card" to show "Dataset Volume" (from CSVs) instead of "Samples" (from Mongo).

### Phase 3: Validation
- Verify that recording a new gesture in **Training** and downloading it to the local CSV folder (and subsequently uploading it to the server) updates the **Gesture Insights** dashboard.

## 5. Success Criteria
- User sees real-time updates of their dataset volume across all CSV files.
- The "Reliability Index" accurately reflects real-world performance from the Playground.
- No more confusion about "missing data" due to MongoDB/CSV synchronization issues.
