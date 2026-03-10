# Video Library + Upload Integration Plan

## Goal
Add a minimal video-processing workflow:
- Upload video (from Training / Playground cards).
- Process in `worker-video-processor`.
- Store up to **5** processed videos.
- Manage and view status in a **Video Library** page.

No separate processing page.

## UX Structure

### 1) Upload Entry Points
Add a small "Upload Video" card in:
- **Training** page
- **Realtime AI Playground** page

Each card should:
- Open an upload modal or route to a small upload form.
- After submit, show inline progress (% + status).
- Include a "View in Video Library" link.

### 2) Video Library Page
New page: **Video Library**
- List up to 5 items.
- Each item shows:
  - name
  - status: `queued | processing | completed | failed`
  - created time
  - progress %
  - actions: view/download, delete
- Auto-delete oldest items when adding the 6th.

## Backend Contracts (Minimal)

### Worker API (already exists)
- `POST /v1/jobs/process` (multipart)
- `GET  /v1/jobs/{job_id}`

### Backend API (new)
Add lightweight proxy endpoints in backend:

1. `POST /video-library/upload`
   - Accepts video file + optional metadata.
   - Forwards to worker `POST /v1/jobs/process`.
   - Records job in registry (local JSON or DB).

2. `GET /video-library`
   - Returns all tracked jobs (max 5).

3. `GET /video-library/{id}`
   - Returns job + status (by polling worker if needed).

4. `DELETE /video-library/{id}`
   - Deletes registry entry + local artifacts.

### Storage
Minimal registry file:
- `backend/data/video_library.json`
- Keep metadata: `id`, `name`, `status`, `created_at`, `result`

## Frontend Routing

Add route: `/video-library`
- Similar layout to Model Library.
- Use table/cards with status badges.

## Status Flow

1. Upload → backend stores entry as `queued`.
2. Backend kicks worker job → status `processing`.
3. Frontend polls `/video-library/{id}` until `completed`.
4. Update list view.

## Constraints
- Hard cap: 5 items.
- Max file size: define limit in backend (e.g. 200MB).
- Allowed formats: mp4, avi, mov.

## Success Criteria
- Upload from Training/Playground works.
- Status updates appear.
- Processed video is downloadable.
- Library never exceeds 5 items.

