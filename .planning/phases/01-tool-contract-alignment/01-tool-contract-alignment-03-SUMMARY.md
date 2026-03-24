---
phase: 01-tool-contract-alignment
plan: "03"
subsystem: testing
tags: [testing, deep_research, sse, history, reducer, open_url]
requires:
  - phase: 01-tool-contract-alignment
    provides: Backend and frontend canonical open_url contracts from plans 01-01 and 01-02.
provides:
  - Queued deep-research API regression coverage proves the 202 background response shape is unchanged.
  - UI history, SSE, reducer, and timeline regressions now assert open_url across stored and streamed events.
  - Phase 1 validation gates pass across backend and frontend suites.
affects: [testing, deep_research, ui, telemetry]
tech-stack:
  added: []
  patterns:
    - Queue-envelope stability is validated independently from runtime tool-contract changes.
    - End-to-end UI regressions assert canonical tool names while preserving open_page action semantics.
key-files:
  created:
    - .planning/phases/01-tool-contract-alignment/01-tool-contract-alignment-03-SUMMARY.md
  modified:
    - backend/tests/api/test_agent_run_route.py
    - src/tests/frontend-api/run-history.integration.test.ts
    - src/tests/frontend-api/runs.stream.test.ts
    - src/tests/frontend/state.test.ts
    - src/tests/frontend/timeline.test.ts
key-decisions:
  - Kept plan 03 focused on regression coverage; no production logic changes were needed beyond prior plan work.
  - Validated the full phase with the repo’s current Vitest command because --runInBand is not supported by Vitest 4 in this repo.
patterns-established:
  - Contract-renames require queue-path tests plus UI history/stream/reducer/timeline coverage before phase closeout.
  - Phase validation commands should match the repo’s actual test runner flags, not stale plan defaults.
requirements-completed: [TOOL-01, TOOL-02]
duration: 18min
completed: 2026-03-24
---

# Phase 01: Tool Contract Alignment Summary

**Regression coverage now proves queued deep-research responses stay stable while `open_url` flows through history, SSE, reducer, and timeline surfaces**

## Performance

- **Duration:** 18 min
- **Started:** 2026-03-24T02:16:00-04:00
- **Completed:** 2026-03-24T02:21:00-04:00
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Added an explicit queued deep-research route regression proving the 202 background envelope stayed unchanged.
- Updated run history, SSE, reducer, and timeline test fixtures to use `open_url` while preserving `open_page`.
- Ran the targeted and full phase validation gates successfully across backend and frontend suites.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add queued deep-research and shared-runtime regression coverage for the renamed tool contract** - `a274825` (test)
2. **Task 2: Add end-to-end UI event-history regressions for open_url while preserving open_page traces** - `8780f02` (test)

## Files Created/Modified
- `backend/tests/api/test_agent_run_route.py` - Deep-research queued-response regression documents unchanged 202 background shape.
- `src/tests/frontend-api/run-history.integration.test.ts` - Stored run-history fixtures now use `open_url`.
- `src/tests/frontend-api/runs.stream.test.ts` - SSE tool-call fixtures now use `open_url`.
- `src/tests/frontend/state.test.ts` - Reducer regression inputs now use `open_url`.
- `src/tests/frontend/timeline.test.ts` - Timeline helper regressions now use `open_url`.

## Decisions Made
- Kept plan 03 test-only because plans 01-01 and 01-02 already supplied the required production changes.
- Used `npm test` as the valid full-suite fallback after confirming `vitest run --runInBand` is not supported in this repo.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Replaced a stale frontend full-suite command during final verification**
- **Found during:** Task 2 (Add end-to-end UI event-history regressions for open_url while preserving open_page traces)
- **Issue:** The plan’s final command used `npm test -- --runInBand`, but Vitest 4 in this repo rejects `--runInBand` as an unknown option.
- **Fix:** Verified the package script and reran the full frontend suite with `npm test`, which maps to the valid `vitest run` command for this repository.
- **Files modified:** None
- **Verification:** `python -m pytest backend/tests -q` and `npm test`
- **Committed in:** N/A (verification-only adjustment)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** No product scope changed. The deviation corrected a stale validation command so phase completion claims stay evidence-based.

## Issues Encountered
- None beyond the stale full-suite Vitest flag discovered during final verification.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 1 is fully validated and ready to hand off to Phase 2 deep-agents lifecycle work.
- The canonical retrieval contract is now consistently `web_search` plus `open_url` across backend, frontend, and regression coverage.

---
*Phase: 01-tool-contract-alignment*
*Completed: 2026-03-24*
