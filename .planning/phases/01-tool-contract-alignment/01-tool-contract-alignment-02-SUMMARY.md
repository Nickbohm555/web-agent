---
phase: 01-tool-contract-alignment
plan: "02"
subsystem: ui
tags: [frontend, telemetry, contracts, zod, open_url]
requires: []
provides:
  - Frontend canonical schemas and browser contracts now expose open_url instead of web_crawl.
  - Fetch-route observability and state normalization emit open_url while preserving open_page retrieval semantics.
  - Frontend contract and observability tests lock the renamed tool contract end to end.
affects: [ui, telemetry, run-history, sse, testing]
tech-stack:
  added: []
  patterns:
    - Exact-name frontend contracts stay aligned with backend canonical tool names.
    - Retrieval action semantics remain distinct from tool-name literals.
key-files:
  created:
    - .planning/phases/01-tool-contract-alignment/01-tool-contract-alignment-02-SUMMARY.md
  modified:
    - src/frontend/contracts/run-events.ts
    - src/frontend/contracts.ts
    - src/frontend/client/browser-contracts.ts
    - src/core/telemetry/observability-logger.ts
    - src/frontend/routes/fetch.ts
    - src/frontend/routes/runs.ts
    - src/frontend/client/state.ts
    - src/tests/frontend-api/run-events.contracts.test.ts
    - src/tests/frontend-api/observability-correlation.test.ts
key-decisions:
  - Kept retrieval action values on open_page even while changing canonical tool names to open_url.
  - Updated exact-name schema, route emission, and reducer normalization together to avoid runtime/event drift.
patterns-established:
  - Browser contract literals mirror canonical run-event schema values exactly.
  - Telemetry derives open_page from open_url instead of overloading the tool name itself.
requirements-completed: [TOOL-01, TOOL-02]
duration: 22min
completed: 2026-03-24
---

# Phase 01: Tool Contract Alignment Summary

**Frontend contracts, telemetry, and reducers now emit `open_url` canonically while keeping `open_page` as the observable retrieval action**

## Performance

- **Duration:** 22 min
- **Started:** 2026-03-24T02:12:00-04:00
- **Completed:** 2026-03-24T02:16:00-04:00
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments
- Replaced `web_crawl` with `open_url` in canonical frontend schemas, browser contracts, and contract tests.
- Updated fetch-route telemetry, observability mapping, and state normalization to emit `open_url`.
- Refreshed the live frontend container after the frontend changes so the running service reflects the new contract.

## Task Commits

Each task was committed atomically:

1. **Task 1: Update frontend schemas and browser parsers to make open_url canonical** - `f2eee63` (feat)
2. **Task 2: Align telemetry and event normalization to emit open_url but still map to open_page** - `f805947` (feat)

## Files Created/Modified
- `src/frontend/contracts/run-events.ts` - Canonical run-event schema now accepts `web_search` and `open_url`.
- `src/frontend/contracts.ts` - Shared frontend contracts export the renamed tool schema.
- `src/frontend/client/browser-contracts.ts` - Browser parser and event types now use `open_url`.
- `src/core/telemetry/observability-logger.ts` - Telemetry maps `open_url` to `open_page`.
- `src/frontend/routes/fetch.ts` - Fetch route emits `open_url` for started, succeeded, and failed tool events.
- `src/frontend/routes/runs.ts` - Run-event normalization switches on `open_url`.
- `src/frontend/client/state.ts` - Reducer/state helpers treat `open_url` as the page-opening tool.
- `src/tests/frontend-api/run-events.contracts.test.ts` - Contract tests reject stale `web_crawl` events.
- `src/tests/frontend-api/observability-correlation.test.ts` - Observability tests prove `open_url` still yields `open_page`.

## Decisions Made
- Treated the failed HTML fetch response as a telemetry mismatch, not a route bug, because the canonical schema had already moved to `open_url`.
- Refreshed only the existing `web-agent` frontend container to avoid recreating the backend stack from the worktree namespace.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed fetch-route telemetry after the schema rename exposed a runtime mismatch**
- **Found during:** Task 2 (Align telemetry and event normalization to emit open_url but still map to open_page)
- **Issue:** `emitToolCallFailed(...)` still emitted `web_crawl`, which caused canonical event validation to throw and Express to return an HTML error page.
- **Fix:** Updated fetch-route emission plus observability/state normalization branches to use `open_url`.
- **Files modified:** `src/core/telemetry/observability-logger.ts`, `src/frontend/routes/fetch.ts`, `src/frontend/routes/runs.ts`, `src/frontend/client/state.ts`
- **Verification:** `npm test -- src/tests/frontend-api/observability-correlation.test.ts src/tests/frontend-api/run-events.contracts.test.ts`
- **Committed in:** `f805947`

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** The deviation was required to keep runtime telemetry aligned with the renamed schema. No scope creep beyond planned normalization work.

## Issues Encountered
- `docker compose up -d frontend` from the worktree created a separate project namespace and conflicted with port `8000`; refreshing the existing `web-agent` project with `--no-deps` resolved it cleanly.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Run history, SSE, reducer, and timeline surfaces can now consume `open_url` without further contract changes.
- The live frontend container has been refreshed with the new telemetry behavior.

---
*Phase: 01-tool-contract-alignment*
*Completed: 2026-03-24*
