---
phase: 04-deep-agents-research-fan-out
plan: 02
subsystem: api
tags: [deepagents, runtime, artifacts, progress, pytest]
requires:
  - phase: 04
    provides: fan-out supervisor and retrieval-tool foundation from 04-01
provides:
  - delegated subquestion execution through the deep-research runtime
  - per-subquestion artifact paths and progress records on saved jobs
  - normalized evidence aggregation from subagent outputs
affects: [deep_research_runtime, deep_research_execution, phase-05]
tech-stack:
  added: []
  patterns: [typed progress records on jobs, lazy Deep Agents imports for local testability]
key-files:
  created:
    - backend/agent/deep_research_artifacts.py
    - backend/agent/deep_research_progress.py
  modified:
    - backend/agent/deep_research_execution.py
    - backend/agent/deep_research_runtime.py
    - backend/tests/agent/test_deep_research_runtime.py
    - backend/agent/schemas/deep_research.py
    - backend/agent/schemas/deep_research_subagent.py
    - backend/agent/deep_agents/schemas/persisted_status.py
    - backend/agent/deep_agents/supervisor.py
key-decisions:
  - "Store progress as typed Pydantic records on DeepResearchJob so the runtime keeps inspectable state without raw dict drift."
  - "Normalize old deep-agents imports lazily so local tests can import the runtime before the deepagents package is installed."
patterns-established:
  - "execute_research_waves(...) accepts focused seams for supervisor construction and delegated subquestion execution."
  - "Per-subquestion artifact paths live under /workspace/research/{job_id}/ and are derived deterministically from question slugs."
requirements-completed: [RSCH-01, RSCH-02]
duration: 1min
completed: 2026-03-24
---

# Phase 4: Deep Agents Research Fan-Out Summary

**Deep-research runtime now delegates planned subquestions, records progress and artifact paths per thread, and aggregates normalized evidence back onto the saved job**

## Performance

- **Duration:** 1 min
- **Started:** 2026-03-24T07:03:56Z
- **Completed:** 2026-03-24T07:05:05Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments
- Replaced the placeholder wave executor with a delegated execution path that validates typed subagent results and updates `wave_count` from the real subquestion set.
- Added deterministic artifact-path and progress-record helpers so each delegated research thread leaves inspectable state on the job.
- Extended runtime tests to prove progress, artifact paths, and normalized source aggregation through the real `execute_research_waves(...)` path.

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend runtime tests for fan-out progress, artifact paths, and normalized evidence** - `6bf084a` (`test`)
2. **Task 2: Add artifact/progress modules and replace the placeholder wave executor with Deep Agents fan-out wiring** - `5319e70` (`feat`)

## Files Created/Modified
- `backend/agent/deep_research_artifacts.py` - Deterministic artifact-path builder and typed artifact records for delegated subquestions.
- `backend/agent/deep_research_progress.py` - Typed per-subquestion progress helpers for saved jobs.
- `backend/agent/deep_research_execution.py` - Real fan-out execution path that validates delegated results and aggregates normalized sources.
- `backend/agent/deep_research_runtime.py` - Runtime wiring that carries the configured supervisor builder into execution.
- `backend/tests/agent/test_deep_research_runtime.py` - Runtime integration coverage for progress, artifacts, and evidence aggregation.
- `backend/agent/schemas/deep_research.py` - Added job-level progress and artifact fields.
- `backend/agent/schemas/deep_research_subagent.py` - Expanded artifact records to carry subanswers and evidence.
- `backend/agent/deep_agents/schemas/persisted_status.py` - Narrow Python 3.9-compatible optional annotation fix for local test execution.
- `backend/agent/deep_agents/supervisor.py` - Lazy-loads Deep Agents imports to keep runtime imports testable before dependency installation.

## Decisions Made
- Kept the runtime direct by injecting only the supervisor-builder and delegated-subquestion seams instead of introducing a generic orchestration runner.
- Stored inspectable fan-out state on `DeepResearchJob` so downstream verification and synthesis can read artifacts and progress directly.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Removed eager Deep Agents imports from runtime-adjacent modules**
- **Found during:** Task 2 (fan-out execution wiring)
- **Issue:** The local Python 3.9 environment does not have `deepagents` installed, so importing the existing deep-agents supervisor module crashed test collection before the runtime could be exercised.
- **Fix:** Moved the `deepagents` and backend-factory imports behind function boundaries and applied a narrow Optional-annotation compatibility fix in `PersistedStatusArtifact`.
- **Files modified:** `backend/agent/deep_agents/schemas/persisted_status.py`, `backend/agent/deep_agents/supervisor.py`
- **Verification:** `pytest backend/tests/agent/test_deep_research_runtime.py -q` and `pytest backend/tests/agent/test_deep_research_subagents.py -q`
- **Committed in:** `5319e70`

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** The fix was required to execute the planned runtime tests in this workspace and did not change the intended Deep Agents runtime surface.

## Issues Encountered

- The local workspace still does not have `deepagents` installed, so the compatibility smoke test remains a skip until the package is added to the active interpreter environment.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 4 is complete: runtime fan-out, artifact paths, and normalized evidence aggregation are in place.
- Phase 5 can now enforce and consume evidence-bearing subagent outputs without first building new runtime plumbing.

## Self-Check: PASSED
