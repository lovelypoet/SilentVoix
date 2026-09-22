# Documentation Index

This directory now contains only docs that match the current SilentVoix scope: a model testing ground with runtime-split inference services and external training workflows.

## Start Here

- `instruction.md`: local development setup and run instructions
- `migration_guide.md`: user-facing migration from in-app training to model upload
- `runtime_service_contract.md`: backend-to-runtime service API contract

## Active Architecture Docs

- `dependency_restructure_plan.md`: active runtime-split priority and rollout
- `backend_cleanup_pth_migration.md`: backend migration status and cleanup order
- `fusion_preprocessing_worker_plan.md`: gloved-hand fusion preprocessing worker plan
- `realtime_ai_playground_model_import.md`: model upload and playground import behavior
- `emotion_recognition.md`: in-browser face emotion recognition (MediaPipe + ONNX FER+)
- `LIVEWS_SENSOR_SCHEMA.md`: sensor WebSocket payload contract

## Active Product / Admin Docs

- `csv_library_admin_plan.md`: admin dataset controller plan and shipped status
- `model_monitor_dashboard_restructure.md`: monitoring dashboard direction
- `profile_monitoring_restructure.md`: operator profile settings direction

## Engineering Spec & Project Docs

- `transformation.md`: V-Hand engineering spec, canonical-stack decision, data contracts
- `agents.md`: competition/QA sprint directives (note: describes a React frontend; the actual frontend is Vue 3)
- `vercel_deployment.md`: deploying the `vue-next/` frontend to Vercel as a demo
- `plan.md`: legacy landing-page master plan (Next.js concept, predates the current Vue 3 `vue-next/` app — kept for historical reference only)

## Scope Rule

Removed documents were legacy training specs, research notes, internal briefings, or one-off snippets from the previous training-first app. If a capability is still real, it should be documented here in its current runtime/testing-ground form rather than preserved as a deprecated design note.
