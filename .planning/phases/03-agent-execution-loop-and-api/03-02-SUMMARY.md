---
phase: 03-agent-execution-loop-and-api
plan: 02
subsystem: backend-api-transport
tags:
  - python
  - fastapi
  - pydantic
  - pytest
  - langgraph
requires:
  - 03-01
provides:
  - strict API request and success-response contracts for one prompt-driven agent run
  - explicit runtime-error to HTTP error-envelope mapping for bounded failure modes
  - frontend-callable `POST /api/agent/run` route wired to the Phase 03 runtime facade
  - deterministic route integration coverage for validation, success, and mapped runtime failures
  - phase-completion updates for roadmap and active planning state
affects:
  - backend/api/contracts.py
  - backend/api/errors.py
  - backend/api/routes/agent_run.py
  - backend/main.py
  - backend/app/main.py
  - backend/tests/api/test_agent_run_route.py
  - backend/requirements.txt
  - .planning/ROADMAP.md
  - .planning/STATE.md
tech-stack:
  added: []
  patterns:
    - contract-first FastAPI route boundary over the internal agent runtime
    - explicit runtime failure category to HTTP status and machine-code mapping
    - single synchronous request-response agent execution seam for frontend integration
    - route tests driven by deterministic runtime stubs instead of live providers
key-files:
  created:
    - backend/api/__init__.py
    - backend/api/contracts.py
    - backend/api/errors.py
    - backend/api/routes/__init__.py
    - backend/api/routes/agent_run.py
    - backend/main.py
  modified:
    - backend/app/main.py
    - backend/tests/api/test_agent_run_route.py
    - backend/requirements.txt
    - .planning/ROADMAP.md
    - .planning/STATE.md
key-decisions:
  - Keep the external API envelope narrow and additive-safe by filtering route responses through dedicated Pydantic models.
  - Map known runtime failure categories to stable HTTP statuses and machine-readable error codes instead of generic 500s.
  - Reuse the runtime facade from Plan 03-01 directly from FastAPI app state so the route triggers exactly one bounded run per request.
  - Close Phase 03 by advancing planning focus to the Phase 04 frontend prompt execution surface.
duration: unknown
completed: 2026-03-17
---

# Phase 03 Plan 02: Agent Execution Loop and API Summary

Delivered the HTTP transport seam for Phase 03: one stable `POST /api/agent/run` endpoint that validates prompt input, executes exactly one bounded agent run, and returns either a normalized answer envelope or an explicit API error payload.

## Outcome

Task 1 (`82326d5`) added the request and response models in [backend/api/contracts.py](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/api/contracts.py), the API error envelope in [backend/api/errors.py](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/api/errors.py), and initial route-contract coverage in [backend/tests/api/test_agent_run_route.py](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/tests/api/test_agent_run_route.py). The API boundary now trims prompt input, forbids unknown request fields, guarantees required success fields (`run_id`, `status`, `final_answer`, `tool_call_count`, `elapsed_ms`, `metadata`), and maps runtime failure categories into stable machine-readable error codes.

Task 2 (`5501ccb`) added the FastAPI route in [backend/api/routes/agent_run.py](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/api/routes/agent_run.py), wired the app in [backend/main.py](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/main.py), and exported the ASGI entrypoint through [backend/app/main.py](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/app/main.py). The backend now exposes `POST /api/agent/run`, resolves the runtime facade from app state, invokes it once per request, and returns only contract-approved fields through `response_model` filtering and explicit JSON error responses.

Task 3 (`a580644`) completed deterministic integration coverage in [backend/tests/api/test_agent_run_route.py](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/tests/api/test_agent_run_route.py). The tests lock down malformed-payload rejection, trimmed-prompt success behavior, and explicit error mapping for bounded failure classes including loop-limit, tool-failure, and provider-failure cases.

## Verification

Recorded execution outcomes for this iteration:
- `npm install` completed successfully.
- `npm run typecheck` completed successfully.
- `npm run test` passed with `19` test files and `104` tests passing.
- `npm run build` completed successfully.
- `pytest backend/tests -q` passed with `67` tests.

## Phase Completion Update

[`.planning/ROADMAP.md`](/Users/nickbohm/Desktop/Tinkering/web-agent/.planning/ROADMAP.md) now marks Phase 03 and both of its plans complete. [`.planning/STATE.md`](/Users/nickbohm/Desktop/Tinkering/web-agent/.planning/STATE.md) advances the active focus to Phase 04, Plan 01 (`04-01`), which starts the frontend prompt execution surface.

## Commit Traceability

- `03-02-task1` (`82326d5`): created the API contracts, error envelope, and initial contract tests.
- `03-02-task2` (`5501ccb`): added the run route, FastAPI app wiring, and entrypoint integration.
- `03-02-task3` (`a580644`): finalized deterministic route tests for validation, success, and mapped runtime failures.

## Deviations

The plan executed as written. No implementation-scope deviations were required beyond running the repository validation sequence again while closing the phase.
