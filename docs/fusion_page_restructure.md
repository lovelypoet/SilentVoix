# Fusion Page Restructure Plan (v1)

## Goal
Unify training UX by making fusion workflows first-class pages (not just cards), and repurpose the unused Guided Lessons area into a practical real-time testing tool.

## Decision Summary
- Early Fusion and Late Fusion should be grouped under one dedicated **Fusion** page entry (same level as Sensor Training).
- Guided Lessons card in `Training.vue` should be replaced by **Realtime AI Playground**.

## Why This Change
Current inconsistency:
- Early Fusion behavior is mostly data capture/export.
- Late Fusion behavior includes dataset selection, training, artifacts, and prediction.

Keeping both as cards inside generic training causes mixed mental models. A dedicated Fusion page makes mode boundaries explicit and easier to extend.

## Proposed IA (Information Architecture)

### Left/Main Navigation
- Dashboard
- Training
- Sensor Training
- Fusion (new dedicated route)
- Library / CSV Library (role-based as is)

### Fusion Page Layout
Top-level mode switch/tabs:
1. **Early Fusion**
2. **Late Fusion**

Early tab:
- camera + sensor capture workflow
- synchronized export
- no training action

Late tab:
- dataset pair readiness
- run training
- job status
- artifact download
- test prediction

## Training Page Card Changes
In `Training.vue` cards:
- Keep `Free Practice`
- Replace `Guided Lessons` with `Realtime AI Playground`
- Remove fusion cards from Training page once dedicated Fusion route is stable

## Realtime AI Playground Scope
MVP:
- live camera preview + hand landmarks
- sensor stream state
- run active model prediction in real time
- confidence + top-k classes

Future:
- side-by-side model comparison
- latency chart
- session replay

## Route Proposal
- `/fusion` (new parent page)
  - internal tabs/sections for Early and Late
- Keep temporary compatibility redirects:
  - `/early-fusion-training` -> `/fusion?tab=early`
  - `/late-fusion-training` -> `/fusion?tab=late`

## Migration Steps
1. Create `Fusion.vue` container page with tab state.
2. Move existing Early Fusion UI into Fusion/Early section.
3. Move existing Late Fusion UI into Fusion/Late section.
4. Add route redirects for backward compatibility.
5. Update `Training.vue` cards (replace Guided Lessons with Realtime AI Playground).
6. QA role gating (`editor/admin`) and route guards.
7. Remove obsolete routes after verification period.

## Acceptance Criteria
- User can access both Early and Late from one Fusion page.
- Training page no longer shows Guided Lessons.
- Realtime AI Playground card is visible and navigable.
- Existing deep links to old fusion routes continue to work via redirect.
- No lint/build regressions.

## Risks / Notes
- Current Late Fusion page includes live CV helper; decide whether to keep it in Late tab or move to Playground for cleaner separation.
- Keep API contracts stable during route migration to avoid frontend/backend drift.
