# Admin-Only CSV Library Plan

## Goal
Create an admin-only CSV Library in the web app to inspect, validate, and manage captured CSV datasets without shell/container access.
This page is the first implementation of the **Data Controller**.

## Delivery Contract (Role, Scope, Constraints, Testing)

### Role
- Codex acts as implementation engineer for this plan.
- Primary responsibility: deliver admin-safe CSV Data Controller features incrementally.
- Secondary responsibility: prevent schema-mixing and training misuse through validation gates.

### Scope (In-Scope)
- Admin-only CSV Library backend and frontend work described in this document.
- Dataset classification for all 6 canonical schema types.
- Validation, preview, download, and archive flows.
- Training compatibility checks for dataset selection.

### Out of Scope (Until explicitly requested)
- Model architecture changes.
- Training algorithm tuning/hyperparameter optimization.
- Non-admin dataset management UI.
- Hard-delete data lifecycle policy.

### Constraints
- Server-side admin authorization is mandatory for all `/admin/csv-library/*` endpoints.
- No frontend-only security assumptions.
- Only `.csv` files under approved base directories are accessible.
- Path traversal and unsafe filename patterns must be rejected.
- Dataset type compatibility must be enforced before training selection.
- Never mix incompatible feature dimensions in one training run.

### Testing Rules (Definition of Done)
- Every backend phase must include authz + validation tests.
- Minimum backend checks per phase:
  - admin `200`, non-admin `403`
  - invalid filename/path traversal rejected
  - schema detection and `feature_dim` checks correct
  - compatibility filtering returns only allowed datasets
- Minimum frontend checks per phase:
  - non-admin cannot see/access CSV Library route
  - list/preview/download UX works with API errors surfaced clearly
  - archive flow confirms and refreshes state
- Before moving to next phase:
  - lint/tests pass for touched code
  - API contract changes are reflected in this document

## Scope
- Admin-only backend routes for listing, previewing, downloading, and archiving CSV files.
- Admin-only frontend page for dataset browsing and quality checks.
- Safe file handling with strict access control and auditability.

## Access Control Requirements
- All endpoints must live under `/admin/csv-library/*`.
- All endpoints must enforce admin role authorization server-side.
- Non-admin authenticated users must receive `403`.
- UI route and navigation entry must be hidden for non-admin users.
- Do not rely on frontend-only role checks.

## Data Sources
- Primary file directory: `backend/data/csv_library/active/{schema_id}/`.
- Optional archive directory: `backend/data/csv_library/archive/{schema_id}/`.
- File type: `.csv` only.

## Canonical Schema Registry (6 Types)

Dataset identity is type-first:
- `modality` in `{cv, sensor, fusion}`
- `hand_mode` in `{single, dual}`

Canonical `schema_id` values:
1. `cv_single`
2. `cv_dual`
3. `sensor_single`
4. `sensor_dual`
5. `fusion_single`
6. `fusion_dual`

Expected feature dimensions:
- `cv_single`: `63`
- `cv_dual`: `126`
- `sensor_single`: `11`
- `sensor_dual`: `22`
- `fusion_single`: `74`
- `fusion_dual`: `148`

Required metadata (per file record):
- `schema_id`
- `schema_version`
- `modality`
- `hand_mode`
- `feature_dim`
- `label_column` (default: `label`)
- `timestamp_column` (default: `timestamp_ms`)

## API Design (Admin Only)

### 1. List files
`GET /admin/csv-library/files`

Response fields (per file):
- `name`
- `size_bytes`
- `modified_at`
- `schema_id`
- `schema_version`
- `modality`
- `hand_mode`
- `feature_dim`
- `row_count`
- `columns`
- `label_summary` (top labels + counts)
- `timestamp_range` (`start_ms`, `end_ms`)
- `health_flags` (array)

Notes:
- Use cached metadata for row count and summaries to avoid re-parsing large files every request.

### 2. Preview rows
`GET /admin/csv-library/files/{name}/preview?limit=100&offset=0`

Response:
- `name`
- `header` (array)
- `rows` (2D array or objects)
- `total_rows`
- `limit`
- `offset`
- `schema_id`
- `schema_version`
- `schema_check`
- `health_flags`

Rules:
- Cap `limit` (e.g., max 500).
- Reject non-CSV or invalid filename.

### 3. File stats
`GET /admin/csv-library/files/{name}/stats`

Response:
- `row_count`
- `column_count`
- `schema_id`
- `schema_version`
- `expected_feature_dim`
- `actual_feature_dim`
- `missing_values_count`
- `duplicate_timestamp_count`
- `label_distribution`
- `timestamp_range`
- `schema_mismatch_details`
- `health_flags`

### 4. Download file
`GET /admin/csv-library/files/{name}/download`

Behavior:
- Streams file as attachment.
- Includes safe content headers.

### 5. Archive file (soft delete)
`POST /admin/csv-library/files/{name}/archive`

Behavior:
- Move file from `csv_library/active/{schema_id}/` to `csv_library/archive/{schema_id}/`.
- Do not hard delete in MVP.

Response:
- `status`
- `from_path`
- `to_path`
- `archived_at`

## Health Flags (MVP)
Use these flags in list/stats endpoints:
- `schema_mismatch`
- `missing_required_columns`
- `empty_file`
- `duplicate_timestamps`
- `timestamp_not_monotonic`
- `possible_channel_order_issue`
- `feature_dim_mismatch`
- `unknown_schema`

## Security + Safety
- Strict filename sanitization:
  - Allow only basename, deny `..`, `/`, null bytes.
  - Allowlist extension `.csv`.
- File access restricted to known base directories only.
- Preview parser limits:
  - Max file size for full stats parse (configurable).
  - Timeout/streaming parse for very large files.
- Archive operation should be atomic where possible.
- Add request logging for all admin file operations.
- Reject training picker usage when `schema_id` is not compatible with selected pipeline/mode.

## Frontend (Admin)

### Page: `CSV Library`
- Table view with:
  - filename, size, updated time, `schema_id`, rows, quick health badge.
- Filters:
  - `schema_id`, modality, hand_mode, schema_version, date range, filename contains, label contains.
- Row actions:
  - Preview, Download, Archive.

### Preview panel
- Header list.
- Paged row table.
- Validation summary badges.
- Label distribution chart (optional).

### UX rules
- Destructive action must show confirmation modal.
- Archive button disabled while action in progress.
- Clear error messages for permission and file parsing failures.

## Suggested Implementation Phases

### Phase 1 (MVP)
- Backend: `files`, `preview`, `download` endpoints.
- Frontend: list + preview + download + `schema_id` filter.
- Admin-only access enforcement.

### Phase 2
- Backend: `stats` endpoint + full schema registry checks.
- Frontend: health badges + modality/mode/schema filters.

### Phase 3
- Backend: `archive` endpoint + audit log.
- Frontend: archive flow + archived files toggle.

### Phase 4
- Backend: training-picker compatibility endpoint:
  - e.g. `GET /admin/csv-library/compatible?pipeline=early&mode=single`
- Frontend: expose only compatible datasets in training pages.

## Test Plan

### Backend
- AuthZ tests: admin `200`, non-admin `403`.
- Path traversal tests rejected.
- Invalid filename/extension rejected.
- Large file preview limit enforced.
- Archive move success/failure behavior.
- Schema registry detection tests for all 6 `schema_id` types.
- `feature_dim` validation tests (`63/126/11/22/74/148`).
- Compatibility filter tests (early single -> only `fusion_single`, early dual -> only `fusion_dual`).

### Frontend
- Admin route hidden for non-admin.
- API permission errors surfaced correctly.
- Table/preview pagination works.
- Archive confirmation flow works and refreshes list.

## Open Decisions
- Should archived files remain downloadable from UI?
- Should row count/stats be precomputed in background jobs for very large files?
- Should CSV metadata be persisted in Mongo for faster list rendering?

## Acceptance Criteria
- Only admins can use CSV Library routes and UI.
- Admin can list/preview/download CSVs without shell access.
- Admin can archive CSVs safely.
- Health flags help detect bad captures before training.
- CSV Library can classify and filter all 6 schema types.
- Dataset compatibility checks prevent wrong-schema training selection.
