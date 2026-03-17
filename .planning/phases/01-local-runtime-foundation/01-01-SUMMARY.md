---
phase: 01-local-runtime-foundation
plan: 01
subsystem: local-runtime
tags:
  - docker-compose
  - docker
  - fastapi
  - express
requires: []
provides:
  - one-command local runtime contract for backend and frontend
  - required API key interpolation before container startup
  - health-gated frontend dependency on backend readiness
affects:
  - docker-compose.yml
  - backend/Dockerfile
  - frontend/Dockerfile
  - backend/app/main.py
  - backend/tests/test_healthz.py
  - src/frontend/server.ts
tech-stack:
  added:
    - Docker Compose
    - FastAPI
    - Uvicorn
    - Express
  patterns:
    - required Compose environment interpolation with ${VAR:?error}
    - service healthchecks with long-form depends_on
    - minimal health endpoints for container readiness
key-files:
  created:
    - docker-compose.yml
    - backend/Dockerfile
    - frontend/Dockerfile
    - backend/app/main.py
    - backend/tests/test_healthz.py
  modified:
    - src/frontend/server.ts
key-decisions:
  - Keep exactly two Compose services: backend and frontend.
  - Enforce OPENAI_API_KEY and SERPER_API_KEY at Compose interpolation time.
  - Gate frontend startup on backend health instead of container start order alone.
  - Add minimal backend and frontend health endpoints so readiness checks are real.
duration: unknown
completed: 2026-03-17
---

# Phase 01 Plan 01: Define Docker Compose Services and Shared Runtime Wiring Summary

Local Docker runtime now boots around a two-service Compose contract with required key enforcement, explicit local ports, and health-based startup ordering.

## Outcome

Task 1 established [`docker-compose.yml`](/Users/nickbohm/Desktop/Tinkering/web-agent/docker-compose.yml) with exactly `backend` and `frontend`, host port mappings `8000:8000` and `3000:3000`, required interpolation for `OPENAI_API_KEY` and `SERPER_API_KEY`, a backend `/healthz` probe, a frontend `/healthz` probe, and long-form `depends_on` so frontend waits for backend health.

Task 2 added deterministic build definitions in [`backend/Dockerfile`](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/Dockerfile) and [`frontend/Dockerfile`](/Users/nickbohm/Desktop/Tinkering/web-agent/frontend/Dockerfile). To satisfy those healthchecks, the implementation also included a minimal FastAPI backend in [`backend/app/main.py`](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/app/main.py), a backend smoke test in [`backend/tests/test_healthz.py`](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/tests/test_healthz.py), and a frontend health endpoint in [`src/frontend/server.ts`](/Users/nickbohm/Desktop/Tinkering/web-agent/src/frontend/server.ts).

## Verification

Recorded execution outcomes:
- `docker compose --env-file /dev/null config` failed as expected when required keys were absent.
- `OPENAI_API_KEY=test-openai SERPER_API_KEY=test-serper docker compose config` resolved both services successfully.
- `OPENAI_API_KEY=test-openai SERPER_API_KEY=test-serper docker compose build backend frontend` completed successfully.
- `npm install`, `npm run typecheck`, `npm run test`, `npm run build`, and `pytest backend/tests -q` were recorded as passing for the delivered runtime scaffolding.

## Commit Traceability

- `ae89b30` `01-01-task1`
- `e3ab911` `01-01-task2`

## Deviations

The plan executed with one practical addition: minimal backend and frontend `/healthz` handlers were included because the Compose healthchecks introduced by this plan required real endpoints to probe.

Traceability is partially degraded. The matching task commits advance planning metadata, but their `git show --stat --name-status` output does not include the runtime artifact files listed above. Summary claims therefore rely on the current workspace state plus the recorded verification notes already captured during task execution.
