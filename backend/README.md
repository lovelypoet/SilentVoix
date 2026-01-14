# Backend Auth Notes

- Cookie-based JWT auth added at `/auth/login`, `/auth/logout`, `/auth/me`.
- Set `DEFAULT_EDITOR_EMAIL` and `DEFAULT_EDITOR_PASSWORD` in `.env` to auto-seed an editor account on first login attempt.
- Write routes now require role `editor` or higher:
  - POST/PUT/DELETE on `gestures`
  - POST on `training` (save/run/trigger)
  - POST/DELETE on `audio-files`
  - DELETE on `admin/*`
- Frontend sends credentials (`withCredentials: true`) and shows editor-only UI only when logged in.
- To change cookie security, set `COOKIE_SECURE=true` in production (requires HTTPS).