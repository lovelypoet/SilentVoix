# Dashboard Restructure Plan: Model Monitoring (v1)

## Goal
Reposition the dashboard from a user-practice summary into a model-monitoring control surface for runtime health, data quality, and prediction performance.

## Scope Change Summary
Old scope:
- personal practice progress (streaks, warm-up, gestures learned)

New scope:
- model and service health
- input/data drift visibility
- live performance trends
- alert and incident awareness

## Why This Change
The current dashboard in `vue-next/src/views/Dashboard.vue` is optimized for training motivation, but current product direction is model operations. The landing page should answer:
1. Is the model healthy right now?
2. Is incoming data still consistent with training data?
3. Is prediction quality stable across time and segments?
4. Is anything broken or degrading that needs action?

## Current -> Proposed Widget Mapping
Current dashboard cards should be replaced as follows:

1. `Today’s Goal` -> `SLO Status`
- Show: uptime, p95 latency, error rate, throughput (req/min)
- Status color: healthy / warning / critical

2. `Confidence Builder` -> `Active Alerts`
- Show: open alert count by severity
- CTA: open alert center / incident page

3. `Streak Status` -> `Model Version & Rollout`
- Show: active model version, previous version, rollout %/phase
- Add rollback button hook (if authorized)

4. `Total Training Time` -> `Traffic Volume`
- Show: requests per minute/hour and 24h trend delta

5. `Gestures Learned` -> `Data Quality`
- Show: missing feature ratio, schema mismatch count, dropped events

6. `Accuracy Streak` -> `Performance Trend`
- Show: chosen quality metric over time (e.g., F1/accuracy proxy/calibration)
- Include top segment degradation (e.g., device/source)

7. `Recent Activity` -> `Recent Monitoring Events`
- Show: alert triggers, model deploys, drift spikes, incident acknowledgments

8. Hero banner (`Welcome back`) -> `Monitoring Overview`
- Show: environment (prod/staging), monitoring window, last refresh time
- Primary actions: `Open Model Library`, `Investigate Alerts`

## Proposed Dashboard Layout (MVP)
Top row:
- Monitoring Overview (environment + global health badge)
- Active Alerts summary

Second row:
- SLO status (latency/error/uptime/throughput)
- Traffic volume trend

Third row:
- Data quality panel
- Drift panel (feature or distribution drift)

Fourth row:
- Performance trend chart
- Segment breakdown table (best/worst segments)

Bottom:
- Recent monitoring events timeline

## Data Contract Changes
Current backend endpoint (`backend/routes/dashboard_routes.py`) returns only aggregate totals and last activity. Add a monitoring-focused contract:

`GET /dashboard/monitoring`
- `health`
  - `status`: `healthy|warning|critical`
  - `uptime_24h`
  - `error_rate_5m`
  - `latency_p95_ms`
  - `throughput_rpm`
- `alerts`
  - `open_total`
  - `critical`
  - `warning`
  - `latest[]`
- `model`
  - `active_version`
  - `previous_version`
  - `rollout_percent`
  - `last_deploy_at`
- `data_quality`
  - `missing_ratio`
  - `schema_mismatch_count`
  - `drop_rate`
- `drift`
  - `global_score`
  - `top_shifted_features[]`
- `performance`
  - `metric_name`
  - `window`
  - `current_value`
  - `trend[]`
  - `segment_regressions[]`
- `events[]`
  - timestamped monitoring/audit events

Keep legacy `GET /dashboard` temporarily for backward compatibility until frontend migration completes.

## Frontend Implementation Notes
- Replace hardcoded static values in `Dashboard.vue` with API-backed composable state.
- Create a dedicated composable (example: `useMonitoringDashboard.js`) for polling, error state, and transformations.
- Polling interval:
  - default: 30s
  - backoff on repeated failure
- Add explicit `Last updated` timestamp on the page.
- Empty/error states must preserve critical alert visibility.

## Permissions and Access
- Viewer: read-only monitoring
- Editor/Admin: additional actions (acknowledge alert, rollback/deploy hooks if enabled)
- Avoid exposing privileged controls to viewer role.

## Migration Plan
1. Add new backend endpoint and response schema for monitoring.
2. Build frontend composable against mock response fixture.
3. Replace dashboard widgets section-by-section (top to bottom).
4. Add alert and drift trend visualizations.
5. Keep old endpoint and remove only after stabilization.
6. Validate with role-based QA and API failure simulation.

## Acceptance Criteria
- Dashboard primary content is monitoring-first (no practice-first cards remain).
- SLO, alerts, model version, data quality, drift, and performance are visible without navigation.
- Data is live from API with clear refresh and failure handling.
- Role restrictions are respected for actions.
- Legacy `/dashboard` consumers continue working during migration window.

## Out of Scope (This Iteration)
- Full incident management workflow
- Advanced root-cause diagnostics
- Cross-model fleet management views

