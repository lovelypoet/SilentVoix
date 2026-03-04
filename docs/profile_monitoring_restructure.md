# Profile Restructure Plan: Monitoring Operator Settings (v1)

## Goal
Convert Profile from personal/device settings into an operator configuration page for model monitoring workflows.

## Why
Dashboard answers "what is happening now".  
Profile should answer "how this operator wants to monitor and be notified".

## Scope
Replace practice/device-focused profile fields with:
- Identity and role
- Access scope defaults
- Alert preferences
- Dashboard defaults
- Session/security actions

## Information Architecture
1. **Identity**
- Display name
- Email
- Role (read-only badge)

2. **Access Scope**
- Default environments (production/staging/development)
- Default model scope list (optional)

3. **Alert Preferences**
- Channels: in-app, email, slack (toggle)
- Minimum severity: warning or critical
- Quiet hours:
  - enabled
  - start time
  - end time
  - timezone

4. **Dashboard Defaults**
- Default time window (e.g., 1h, 6h, 24h, 7d)
- Auto-refresh interval (seconds)
- Default segment filter (string)

5. **Security**
- Sign out

## API Contract Changes
Extend existing auth profile payloads:

`GET /auth/me` returns:
- `id`
- `email`
- `role`
- `display_name`
- `access_scope`
  - `environments[]`
  - `models[]`
- `operator_preferences`
  - `alert_channels`
    - `in_app`
    - `email`
    - `slack`
  - `alert_min_severity`
  - `quiet_hours`
    - `enabled`
    - `start`
    - `end`
    - `timezone`
  - `dashboard_defaults`
    - `window`
    - `refresh_seconds`
    - `segment_filter`

`PUT /auth/me` accepts partial updates for the same fields.

## Defaults
If fields are missing in existing user docs, backend should return defaults:
- environments: `["production"]`
- models: `[]`
- alert channels: `in_app=true`, `email=false`, `slack=false`
- min severity: `warning`
- quiet hours: disabled, `22:00-07:00`, `UTC`
- dashboard defaults: `window=24h`, `refresh_seconds=30`, `segment_filter=all`

## Migration Notes
- Backward compatible with current users (no required migration script).
- Existing tokens remain valid.
- Existing profile update path remains the same endpoint.

## Acceptance Criteria
- Profile page no longer references glove device settings.
- Operator settings are editable and persisted via `/auth/me`.
- Refreshing the app preserves saved profile preferences.
- Role remains visible and read-only.
