---
phase: 04-frontend-prompt-execution-surface
plan: 02
subsystem: frontend-run-streaming-foundation
tags:
  - typescript
  - express
  - zod
  - vitest
  - browser
  - sse
requires:
  - 04-01
provides:
  - strict typed SSE contracts for run lifecycle and tool-call events
  - browser EventSource subscription plumbing with validation guards and terminal close behavior
  - deterministic reducer semantics for duplicate and out-of-order tool events
  - stable run/tool state records ready for timeline rendering in 04-03
affects:
  - src/frontend/contracts.ts
  - src/frontend/routes/runs.ts
  - src/frontend/client/api-client.ts
  - src/frontend/client/state.ts
  - src/frontend/client/app.ts
  - src/tests/frontend-api/runs.stream.test.ts
  - src/tests/frontend/state.test.ts
tech-stack:
  added: []
  patterns:
    - schema-validated named SSE events shared between the route layer and browser client
    - single active EventSource subscription with explicit terminal and supersession cleanup
    - idempotent reducer merging keyed by `toolCallId`
    - monotonic run-phase guards that reject stale post-terminal updates
key-files:
  created:
    - src/tests/frontend-api/runs.stream.test.ts
    - src/tests/frontend/state.test.ts
  modified:
    - src/frontend/contracts.ts
    - src/frontend/routes/runs.ts
    - src/frontend/client/api-client.ts
    - src/frontend/client/state.ts
    - src/frontend/client/app.ts
key-decisions:
  - Lock tool event names to `web_search` and `web_crawl` in shared contracts so the frontend stream parser fails closed on schema drift.
  - Close the active `EventSource` both on terminal events and before subscribing to a newer run to prevent duplicate listeners and leaked progress streams.
  - Merge tool events by `toolCallId` and preserve the most advanced status while backfilling timestamps and previews from out-of-order frames.
duration: unknown
completed: 2026-03-17
---

# Phase 04 Plan 02: Frontend Prompt Execution Surface Summary

Delivered the live run-streaming foundation for Phase 04: typed SSE event contracts, a guarded browser subscription layer, and a reducer that stays deterministic under duplicate and out-of-order tool updates.

## Outcome

Task 1 (`ba499f3`) extended [src/frontend/contracts.ts](/Users/nickbohm/Desktop/Tinkering/web-agent/src/frontend/contracts.ts) with strict schemas for `run_state`, `tool_call`, `run_complete`, and `run_error`, updated [src/frontend/routes/runs.ts](/Users/nickbohm/Desktop/Tinkering/web-agent/src/frontend/routes/runs.ts) to emit those named SSE frames, and wired [src/frontend/client/api-client.ts](/Users/nickbohm/Desktop/Tinkering/web-agent/src/frontend/client/api-client.ts) to subscribe through `EventSource`, validate every frame, and close cleanly on completion, failure, or superseding reruns. [src/tests/frontend-api/runs.stream.test.ts](/Users/nickbohm/Desktop/Tinkering/web-agent/src/tests/frontend-api/runs.stream.test.ts) locks down valid frame emission, parse-failure handling, and stream lifecycle cleanup.

Task 2 (`64e49ef`) hardened [src/frontend/client/state.ts](/Users/nickbohm/Desktop/Tinkering/web-agent/src/frontend/client/state.ts) so run updates remain monotonic and tool-call records merge idempotently by `toolCallId`, even when events arrive duplicated or out of order. [src/tests/frontend/state.test.ts](/Users/nickbohm/Desktop/Tinkering/web-agent/src/tests/frontend/state.test.ts) verifies deterministic ordering, stale-run filtering, and terminal regression guards, while [src/frontend/client/app.ts](/Users/nickbohm/Desktop/Tinkering/web-agent/src/frontend/client/app.ts) was adjusted to consume the richer reducer output.

## Verification

Recorded execution outcomes for this iteration:
- `npm install` completed successfully.
- `npm run typecheck` completed successfully.
- `npm run test` passed with `22` test files and `114` tests passing.
- `npm run build` completed successfully.

Task commit evidence also records the plan-specific checks:
- `04-02-task1` verified `npm run test -- src/tests/frontend-api/runs.stream.test.ts`.
- `04-02-task2` verified `npm run test -- src/tests/frontend/state.test.ts`.

## Commit Traceability

- `04-02-task1` (`ba499f3`): added shared run-stream schemas, SSE route/client plumbing, and stream contract tests.
- `04-02-task2` (`64e49ef`): implemented idempotent reducer semantics, timeline-ready tool-call state, and reducer coverage.

## Deviations

The plan executed as written. No implementation-scope deviations were required.
