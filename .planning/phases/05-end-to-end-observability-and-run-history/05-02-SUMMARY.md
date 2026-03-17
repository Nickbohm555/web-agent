---
phase: 05-end-to-end-observability-and-run-history
plan: 02
subsystem: backend-observability-correlation
tags:
  - typescript
  - express
  - pino
  - docker
  - vitest
requires:
  - 05-01
provides:
  - run-scoped correlation context with monotonic event sequencing
  - structured backend observability events aligned to the canonical RunEvent contract
  - redaction and truncation safeguards before payloads reach logs
  - docker log configuration suitable for local structured log retrieval
  - parity tests between backend log events and frontend timeline rows
affects:
  - src/core/telemetry/run-context.ts
  - src/core/telemetry/observability-logger.ts
  - src/frontend/server.ts
  - src/frontend/routes/search.ts
  - src/frontend/routes/fetch.ts
  - docker-compose.yml
  - src/tests/frontend-api/observability-correlation.test.ts
tech-stack:
  added: []
  patterns:
    - AsyncLocalStorage-backed run context for automatic correlation metadata propagation
    - pino-emitted JSON lifecycle events validated through the shared frontend RunEvent schema
    - logger-boundary redaction and truncation instead of route-specific payload scrubbing
    - UI-to-log parity checks keyed by run_id, event_seq, and event_type
key-files:
  created:
    - src/core/telemetry/run-context.ts
    - src/core/telemetry/observability-logger.ts
  modified:
    - src/frontend/server.ts
    - src/frontend/routes/search.ts
    - src/frontend/routes/fetch.ts
    - docker-compose.yml
    - src/tests/frontend-api/observability-correlation.test.ts
key-decisions:
  - Initialize run context once at the `/api` boundary so downstream routes inherit correlation metadata without manual parameter plumbing.
  - Reuse the canonical frontend RunEvent parser for backend log validation to keep observability and UI traces on one contract.
  - Apply bounded redaction and truncation in the shared logger helper so search and fetch routes emit safe payloads consistently.
duration: unknown
completed: 2026-03-17
---

# Phase 05 Plan 02: Emit and Correlate Structured Backend Observability Logs Summary

Delivered the correlation layer for Phase 05: structured backend JSON events, stable `run_id` and `event_seq` metadata, safe payload logging, and parity checks against frontend timeline rendering.

## Outcome

Task 1 (`7d6885b`) added [src/core/telemetry/run-context.ts](/Users/nickbohm/Desktop/Tinkering/web-agent/src/core/telemetry/run-context.ts), updated [src/frontend/server.ts](/Users/nickbohm/Desktop/Tinkering/web-agent/src/frontend/server.ts), and introduced initial coverage in [src/tests/frontend-api/observability-correlation.test.ts](/Users/nickbohm/Desktop/Tinkering/web-agent/src/tests/frontend-api/observability-correlation.test.ts). The frontend API boundary now creates a run-scoped async context for each `/api` request, exposes deterministic `run_id` lookup, and owns monotonic `event_seq` generation across promise, timer, and immediate boundaries.

Task 2 (`7a22175`) added [src/core/telemetry/observability-logger.ts](/Users/nickbohm/Desktop/Tinkering/web-agent/src/core/telemetry/observability-logger.ts), instrumented [src/frontend/routes/search.ts](/Users/nickbohm/Desktop/Tinkering/web-agent/src/frontend/routes/search.ts) and [src/frontend/routes/fetch.ts](/Users/nickbohm/Desktop/Tinkering/web-agent/src/frontend/routes/fetch.ts), and expanded [src/tests/frontend-api/observability-correlation.test.ts](/Users/nickbohm/Desktop/Tinkering/web-agent/src/tests/frontend-api/observability-correlation.test.ts). Backend search and crawl routes now emit structured `tool_call_started`, `tool_call_succeeded`, and `tool_call_failed` events through one shared logger that redacts sensitive keys, truncates oversized payloads, and validates each emitted record against the canonical RunEvent contract before it is written to stdout.

Task 3 (`70befa8`) updated [docker-compose.yml](/Users/nickbohm/Desktop/Tinkering/web-agent/docker-compose.yml) and finalized parity assertions in [src/tests/frontend-api/observability-correlation.test.ts](/Users/nickbohm/Desktop/Tinkering/web-agent/src/tests/frontend-api/observability-correlation.test.ts). Local containers now use bounded `json-file` logging, and the regression suite asserts one-to-one parity between backend structured log events and frontend timeline rows using the shared `run_id:event_seq:event_type` identity.

## Verification

Recorded execution outcomes for this summary iteration:
- `npm install` completed successfully.
- `npm run typecheck` completed successfully.
- `npm run test` passed with `25` test files and `129` tests passing.
- `npm run build` completed successfully.

Plan traceability and task evidence:
- `05-02-task1` (`7d6885b`): added run context propagation and correlation-boundary tests.
- `05-02-task2` (`7a22175`): added structured observability logging with redaction and truncation safeguards.
- `05-02-task3` (`70befa8`): finalized Docker logging configuration and UI-log parity assertions.

## Commit Traceability

- `05-02-task1` (`7d6885b`): created the run context utility, wired it at the API boundary, and verified sequence stability across async hops.
- `05-02-task2` (`7a22175`): added the shared observability logger and instrumented search and fetch lifecycle events.
- `05-02-task3` (`70befa8`): configured Docker log rotation and enforced frontend/backend event parity in the observability test suite.

## Deviations

The plan executed as written. No implementation-scope deviations were required.
