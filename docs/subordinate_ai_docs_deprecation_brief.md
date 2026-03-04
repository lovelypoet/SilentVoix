# Subordinate AI CLI Brief: Docs + Deprecation Track

## Mission
Own the documentation and communication side of the scope change:
- from training-focused platform
- to multi-format model testing ground

Do not implement backend runtime logic in this track.

## Product Direction (Authoritative)
- Project is now a **model testing ground**.
- Supported model formats are **curated**, not unlimited.
- Initial curated set:
  - `.tflite`
  - `.keras`
  - `.h5`
  - `.pth`
- Optional next format (separate milestone): `onnx`

## Your Boundaries
- You own:
  - README and all `.md` scope alignment
  - deprecation notices for training features
  - migration notes for users
  - endpoint/status documentation
- You do not own:
  - route/controller/model code changes
  - dependency/runtime migration
  - Docker/runtime debugging

## Required Tasks
1. Update root docs to new scope
   - Rewrite project summary, goals, and feature list to testing-ground positioning.
2. Mark training pipeline as deprecated
   - Add explicit deprecation sections for `/training/*` flows.
3. Publish migration notes
   - “If you used training endpoints before, here is what changes now.”
4. Create endpoint status table
   - `active`, `deprecated`, `removed` columns for key API paths.
5. Align model-format language everywhere
   - Replace “train model in app” wording with “upload exported model package”.

## Files To Update (Minimum)
- `README.md`
- `docs/backend_cleanup_pth_migration.md`
- any docs that still promise in-app training or pipeline feeding

## Required Deliverables
1. A single docs PR (or patch set) containing:
   - scope rewrite
   - deprecation notices
   - endpoint status table
   - migration FAQ
2. A short `CHANGELOG`-style summary section at end of PR description:
   - what changed
   - what was deprecated
   - what remains active

## Definition of Done
- No top-level doc claims “in-app model training” as an active feature.
- Training routes are clearly documented as deprecated or removal-target.
- Testing-ground flow is clear:
  - upload
  - store
  - activate
  - predict
- Supported formats are presented as curated list, not “all formats”.

## Quality Bar
- Use direct, non-ambiguous wording.
- Avoid future promises without milestone tags.
- Keep terminology consistent:
  - “model package”
  - “playground inference”
  - “deprecated training endpoints”

## Handoff Back To Lead AI
When done, provide:
1. Updated file list.
2. 5-10 bullet summary of changed statements.
3. Any unresolved conflicts between old docs and current backend behavior.
