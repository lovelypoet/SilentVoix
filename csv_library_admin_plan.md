# Admin-Only CSV Library Plan

## Goal
Create an admin-only CSV Library in the web app to inspect, validate, and manage captured CSV datasets without shell/container access.

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
- Primary file directory: `backend/data/`.
- Optional archive directory: `backend/data/archive/`.
- File type: `.csv` only.

## API Design (Admin Only)

### 1. List files
`GET /admin/csv-library/files`

Response fields (per file):
- `name`
- `size_bytes`
- `modified_at`
- `mode` (`single` | `dual` | `unknown`)
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
- Move file from `data/` to `data/archive/`.
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

## Frontend (Admin)

### Page: `CSV Library`
- Table view with:
  - filename, size, updated time, mode, rows, quick health badge.
- Filters:
  - mode, date range, filename contains, label contains.
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
- Frontend: list + preview + download.
- Admin-only access enforcement.

### Phase 2
- Backend: `stats` endpoint and health flags.
- Frontend: health badges + filters.

### Phase 3
- Backend: `archive` endpoint + audit log.
- Frontend: archive flow + archived files toggle.

## Test Plan

### Backend
- AuthZ tests: admin `200`, non-admin `403`.
- Path traversal tests rejected.
- Invalid filename/extension rejected.
- Large file preview limit enforced.
- Archive move success/failure behavior.

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
