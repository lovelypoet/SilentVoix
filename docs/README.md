# Documentation Index

This directory now contains only docs that match the current SilentVoix scope: a model testing ground with runtime-split inference services and external training workflows.

## Start Here

- `instruction.md`: local development setup and run instructions
- `migration_guide.md`: user-facing migration from in-app training to model upload
- `runtime_service_contract.md`: backend-to-runtime service API contract

## Active Architecture Docs

- `dependency_restructure_plan.md`: active runtime-split priority and rollout
- `backend_cleanup_pth_migration.md`: backend migration status and cleanup order
- `realtime_ai_playground_model_import.md`: model upload and playground import behavior
- `LIVEWS_SENSOR_SCHEMA.md`: sensor WebSocket payload contract

## Active Product / Admin Docs

- `csv_library_admin_plan.md`: admin dataset controller plan and shipped status
- `model_monitor_dashboard_restructure.md`: monitoring dashboard direction
- `profile_monitoring_restructure.md`: operator profile settings direction

## Scope Rule

Removed documents were legacy training specs, research notes, internal briefings, or one-off snippets from the previous training-first app. If a capability is still real, it should be documented here in its current runtime/testing-ground form rather than preserved as a deprecated design note.
