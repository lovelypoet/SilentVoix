# SilentVoix Java backend

Spring Boot service for SilentVoix, planned to sit alongside the existing Python stack (`api/`, `backend/`, the ML sidecars and workers) and integrate with it over HTTP/WebSocket. It does not replace or port any of the Python services.

**Status:** scaffold only. There are no application classes, endpoints or business logic yet.

## Tech stack

| Area | Choice |
|---|---|
| Language | Java 21 |
| Framework | Spring Boot 4.1.x |
| Build | Maven (no wrapper committed yet — use a local `mvn`) |
| APIs (planned) | REST, WebSocket |
| Integrates with (planned) | Existing FastAPI API (`api/`, port 8000), ML sidecars (8091–8095), Celery + Redis |
| Data stores (existing, unchanged) | PostgreSQL, MongoDB, Redis |

Only `spring-boot-starter` and `spring-boot-starter-test` are declared for now. Add web, WebSocket and data starters when the matching features get built.

## Layout

```
backend-java/
├── pom.xml
└── src/
    ├── main/java/com/silentvoix/backend/   # application code (empty)
    ├── main/resources/application.properties
    └── test/java/com/silentvoix/backend/   # tests (empty)
```

## Constraints to keep

- The ESP32 glove firmware and its WebSocket protocol stay unchanged. Frames are normalized to `silentvoix.sensor_frame.v1` (11 values: `accel[3] + gyro[3] + flex[5]`). See `docs/transformation.md` §8.
- Default port is `8081` (override with `SERVER_PORT`) so it doesn't clash with the existing services.
