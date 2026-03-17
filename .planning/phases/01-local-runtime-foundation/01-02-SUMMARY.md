---
phase: 01-local-runtime-foundation
plan: 02
subsystem: backend-runtime-config
tags:
  - fastapi
  - pydantic-settings
  - docker-compose
  - pytest
  - environment-config
requires:
  - 01-01-define-docker-compose-services-and-shared-runtime-wiring
provides:
  - startup-time validation for OPENAI_API_KEY and SERPER_API_KEY
  - typed reusable backend settings access
  - regression coverage for missing-key and healthy-start behavior
  - demonstrated phase-1 compose failure and success semantics
affects:
  - backend/app/config.py
  - backend/app/main.py
  - backend/requirements.txt
  - backend/tests/test_startup_settings.py
  - backend/tests/conftest.py
  - docker-compose.yml
  - .planning/ROADMAP.md
  - .planning/STATE.md
tech-stack:
  added:
    - pydantic-settings
  patterns:
    - FastAPI lifespan-based startup validation
    - cached typed settings accessor for backend runtime config
    - pytest repo-root path bootstrap for documented backend test command
    - Compose required env interpolation plus health-gated startup verification
key-files:
  created:
    - backend/app/config.py
    - backend/tests/test_startup_settings.py
    - backend/tests/conftest.py
  modified:
    - backend/app/main.py
    - backend/requirements.txt
    - .planning/ROADMAP.md
    - .planning/STATE.md
key-decisions:
  - Validate required provider keys during FastAPI lifespan startup, not lazily inside tools.
  - Keep settings access centralized through a typed cached helper.
  - Preserve Compose-level missing-key enforcement and verify backend/frontend reachability with real probes.
  - Fix the backend test harness so `pytest backend/tests -q` works from the repository root exactly as documented.
duration: unknown
completed: 2026-03-17
---

# Phase 01 Plan 02: Implement Environment Configuration Loading and Startup Validation Summary

Backend runtime now fails deterministically when required provider keys are absent and starts cleanly, with both services reachable, when valid environment variables are present.

## Outcome

Task 1 added typed runtime configuration in [`backend/app/config.py`](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/app/config.py) and wired startup validation in [`backend/app/main.py`](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/app/main.py). The backend now instantiates settings during FastAPI lifespan startup, exposes `/healthz`, and stops boot immediately on missing `OPENAI_API_KEY` or `SERPER_API_KEY`.

Task 2 added regression coverage in [`backend/tests/test_startup_settings.py`](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/tests/test_startup_settings.py) for missing OpenAI key, missing Serper key, and successful startup when both keys are present. A minimal pytest bootstrap file at [`backend/tests/conftest.py`](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/tests/conftest.py) was added so the documented repo-root test command imports the `backend` package correctly.

Task 3 confirmed the phase acceptance path against the existing Compose contract in [`docker-compose.yml`](/Users/nickbohm/Desktop/Tinkering/web-agent/docker-compose.yml): missing keys fail at interpolation time, and placeholder keys are sufficient to boot the backend and frontend to healthy state for local reachability checks.

## Verification

Recorded execution outcomes:
- `npm install` completed successfully.
- `npm run typecheck` completed successfully.
- `npm run test` passed with `19` test files and `104` tests passing.
- `npm run build` completed successfully.
- `pytest backend/tests -q` passed with `4` tests after fixing repo-root import resolution.
- `docker compose --env-file /dev/null config` failed as expected with a required `OPENAI_API_KEY` interpolation error.
- `OPENAI_API_KEY=test-openai SERPER_API_KEY=test-serper docker compose up --build --wait` completed successfully.
- `curl -f http://localhost:8000/healthz` returned `{"status":"ok"}`.
- `curl -f http://localhost:3000/healthz` returned `{"status":"ok"}`.

## Phase Completion Update

[`.planning/ROADMAP.md`](/Users/nickbohm/Desktop/Tinkering/web-agent/.planning/ROADMAP.md) now marks Phase 1 and both of its plans complete. [`.planning/STATE.md`](/Users/nickbohm/Desktop/Tinkering/web-agent/.planning/STATE.md) advances the active focus to Phase 2, Plan 01 (`02-01-implement-serper-backed-web-search-tool-in-python`).

## Commit Traceability

No matching task commits were found for `01-02-task1`, `01-02-task2`, or `01-02-task3` in local git history, so direct task-to-commit traceability is currently unavailable for this plan.

## Deviations

The planned runtime work was already present in the workspace, but the required validation command `pytest backend/tests -q` initially failed with `ModuleNotFoundError: No module named 'backend'`. This iteration added [`backend/tests/conftest.py`](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/tests/conftest.py) to restore the documented test path, then reran the full validation and compose acceptance checks successfully.
