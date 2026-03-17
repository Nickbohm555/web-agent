---
phase: 04-frontend-prompt-execution-surface
plan: 01
subsystem: frontend-run-start-surface
tags:
  - typescript
  - express
  - zod
  - vitest
  - browser
requires:
  - 03-02
provides:
  - typed `POST /api/runs` request and response contracts for run creation
  - an Express route that validates prompt input and returns a generated run identifier
  - a minimal single-screen prompt UI with idle, starting, running, and failed states
  - a typed browser API client and reducer seam ready for live run-event integration in 04-02
affects:
  - src/frontend/contracts.ts
  - src/frontend/routes/runs.ts
  - src/frontend/server.ts
  - src/tests/frontend-api/runs.contracts.test.ts
  - public/index.html
  - src/frontend/client/api-client.ts
  - src/frontend/client/state.ts
  - src/frontend/client/app.ts
  - tsconfig.json
  - src/scraper/extract.ts
tech-stack:
  added: []
  patterns:
    - schema-first run-start contract validation shared between the frontend server and tests
    - minimal browser state machine for one-active-run prompt submission
    - typed client-side normalization of success and error run-start responses
    - single-page frontend shell with explicit submit-state rendering
key-files:
  created:
    - src/frontend/routes/runs.ts
    - src/tests/frontend-api/runs.contracts.test.ts
    - public/index.html
    - src/frontend/client/api-client.ts
    - src/frontend/client/state.ts
    - src/frontend/client/app.ts
  modified:
    - src/frontend/contracts.ts
    - src/frontend/server.ts
    - tsconfig.json
    - src/scraper/extract.ts
key-decisions:
  - Return a narrow run-start response with only `runId` and queued or running status so later timeline work can layer on without breaking the initial contract.
  - Keep `POST /api/runs` in the frontend TypeScript server for Phase 04 so the browser can integrate against a stable local seam before SSE work begins.
  - Model the browser run lifecycle as a strict reducer with one-active-run behavior to prevent invalid regressions during prompt submission.
duration: unknown
completed: 2026-03-17
---

# Phase 04 Plan 01: Frontend Prompt Execution Surface Summary

Delivered the first frontend run-start surface for Phase 04: one prompt form, one `POST /api/runs` contract, and a strict browser state flow that moves from idle to starting to running or failed.

## Outcome

Task 1 (`5436f28`) extended [src/frontend/contracts.ts](/Users/nickbohm/Desktop/Tinkering/web-agent/src/frontend/contracts.ts) with `run_start` request, response, and error-envelope schemas, added the new route in [src/frontend/routes/runs.ts](/Users/nickbohm/Desktop/Tinkering/web-agent/src/frontend/routes/runs.ts), wired it into [src/frontend/server.ts](/Users/nickbohm/Desktop/Tinkering/web-agent/src/frontend/server.ts), and locked down contract behavior in [src/tests/frontend-api/runs.contracts.test.ts](/Users/nickbohm/Desktop/Tinkering/web-agent/src/tests/frontend-api/runs.contracts.test.ts). The frontend server now validates `{ prompt: string }`, rejects malformed payloads through the shared error-envelope path, and returns a generated UUID with a typed queued status.

Task 2 (`c5bd90d`) created the single-screen UI in [public/index.html](/Users/nickbohm/Desktop/Tinkering/web-agent/public/index.html), the typed browser request layer in [src/frontend/client/api-client.ts](/Users/nickbohm/Desktop/Tinkering/web-agent/src/frontend/client/api-client.ts), the reducer in [src/frontend/client/state.ts](/Users/nickbohm/Desktop/Tinkering/web-agent/src/frontend/client/state.ts), and the DOM wiring in [src/frontend/client/app.ts](/Users/nickbohm/Desktop/Tinkering/web-agent/src/frontend/client/app.ts). The browser flow now trims prompt input, blocks duplicate starts while a run is starting or active, surfaces empty-prompt failures without crashing, and renders run status details for the active run identifier.

## Verification

Task commit evidence records the planned verification steps:
- `04-01-task1` verified `npm run test -- src/tests/frontend-api/runs.contracts.test.ts` for valid run-start responses and malformed-payload rejection.
- `04-01-task2` verified `npm run typecheck && npm run test -- src/tests/frontend-api/runs.contracts.test.ts` after wiring the browser client and reducer.

## Commit Traceability

- `04-01-task1` (`5436f28`): added the run-start schemas, Express route, router wiring, and contract tests.
- `04-01-task2` (`c5bd90d`): added the minimal prompt UI, browser API client, reducer, and submit-state rendering flow.

## Deviations

Task 2 also modified [src/scraper/extract.ts](/Users/nickbohm/Desktop/Tinkering/web-agent/src/scraper/extract.ts) and [tsconfig.json](/Users/nickbohm/Desktop/Tinkering/web-agent/tsconfig.json), which were outside the narrow 04-01 artifact list. The summary preserves that traceability from commit `c5bd90d`; the delivered 04-01 outcome itself remained aligned with the plan.
