---
phase: 05-end-to-end-observability-and-run-history
plan: 01
subsystem: frontend-tool-payload-observability
tags:
  - typescript
  - express
  - vitest
  - browser
  - zod
requires:
  - 04-03
provides:
  - canonical run-event schema for UI payload inspection
  - full tool input and output rendering for success and failure events
  - explicit redaction and truncation markers in the timeline and inspector
  - contract tests that block correlation-field and secret-leak regressions
affects:
  - src/frontend/contracts.ts
  - src/frontend/contracts/run-events.ts
  - src/frontend/client/app.ts
  - src/frontend/client/state.ts
  - src/frontend/client/timeline.ts
  - public/index.html
  - src/tests/frontend-api/run-events.contracts.test.ts
tech-stack:
  added: []
  patterns:
    - one canonical zod-validated RunEvent contract shared by render and parsing paths
    - event-sequence-driven timeline rendering with selectable payload inspection
    - explicit payload-safety metadata for redaction and truncation instead of silent omission
key-files:
  created:
    - src/frontend/contracts/run-events.ts
  modified:
    - src/frontend/contracts.ts
    - src/frontend/client/app.ts
    - src/frontend/client/state.ts
    - src/frontend/client/timeline.ts
    - public/index.html
    - src/tests/frontend-api/run-events.contracts.test.ts
key-decisions:
  - Keep one canonical run-event schema for payload inspection so frontend rendering and upcoming backend observability work share the same event shape.
  - Store ordered canonical run events in reducer state and select them by `run_id:event_seq` so payload inspection stays deterministic.
  - Require explicit safety metadata for redaction and truncation so sensitive or oversized payload handling is visible rather than implicit.
duration: unknown
completed: 2026-03-17
---

# Phase 05 Plan 01: Add Full Tool Payload Rendering In UI Summary

Delivered the contract and UI foundation for observability: ordered run events with full tool payload inspection, plus visible payload-safety markers.

## Outcome

Task 1 (`811ad87`) added [src/frontend/contracts/run-events.ts](/Users/nickbohm/Desktop/Tinkering/web-agent/src/frontend/contracts/run-events.ts) and extended [src/frontend/contracts.ts](/Users/nickbohm/Desktop/Tinkering/web-agent/src/frontend/contracts.ts). The frontend now has a canonical `RunEventSchema` with required correlation fields (`run_id`, `event_seq`, `event_type`, `ts`), tool payload slots (`tool_input`, `tool_output`, `error_output`, `final_answer`), helper parsers for single and ordered event lists, and explicit safety metadata for redaction and truncation.

Task 2 (`5d445de`) updated [src/frontend/client/app.ts](/Users/nickbohm/Desktop/Tinkering/web-agent/src/frontend/client/app.ts), [src/frontend/client/state.ts](/Users/nickbohm/Desktop/Tinkering/web-agent/src/frontend/client/state.ts), [src/frontend/client/timeline.ts](/Users/nickbohm/Desktop/Tinkering/web-agent/src/frontend/client/timeline.ts), and [public/index.html](/Users/nickbohm/Desktop/Tinkering/web-agent/public/index.html). The UI now stores canonical run events in reducer state, assigns monotonic `event_seq` values for locally synthesized lifecycle events, renders an ordered event timeline, and shows a dedicated inspector with full input, output, error, and final-answer payload sections plus redaction/truncation badges.

Task 3 (`55150dd`) tightened [src/frontend/contracts/run-events.ts](/Users/nickbohm/Desktop/Tinkering/web-agent/src/frontend/contracts/run-events.ts) and completed [src/tests/frontend-api/run-events.contracts.test.ts](/Users/nickbohm/Desktop/Tinkering/web-agent/src/tests/frontend-api/run-events.contracts.test.ts). The tests now lock down schema acceptance for success and failure events, rejection of missing correlation metadata, rejection of raw secret leakage, enforcement of matching redaction metadata, and ordered-event invariants for `event_seq`.

## Verification

Recorded execution outcomes for this iteration:
- `npm install` completed successfully.
- `npm run typecheck` completed successfully.
- `npm run test` passed with `24` test files and `125` tests passing.
- `npm run build` completed successfully.

Task commit evidence also records the plan-specific verification path:
- `05-01-task1` (`811ad87`) added the canonical contract and focused contract coverage.
- `05-01-task2` (`5d445de`) completed the payload-inspector UI flow for ordered run events.
- `05-01-task3` (`55150dd`) finalized regression checks for payload completeness and safety invariants.

## Commit Traceability

- `05-01-task1` (`811ad87`): created the canonical run-event schema and exported it through the shared frontend contracts surface.
- `05-01-task2` (`5d445de`): wired canonical events into reducer state and rendered the timeline plus payload inspector UI.
- `05-01-task3` (`55150dd`): enforced redaction, truncation, and ordering invariants through focused contract tests.

## Deviations

The plan executed as written. No implementation-scope deviations were required.
