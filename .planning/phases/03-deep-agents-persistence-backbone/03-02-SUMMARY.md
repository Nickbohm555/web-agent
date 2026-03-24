---
phase: 03-deep-agents-persistence-backbone
plan: 02
subsystem: api
tags: [deepagents, postgres, resume, logging, fastapi]
requires:
  - phase: 03-deep-agents-persistence-backbone
    provides: persistence backbone and run-scoped artifact routing
provides:
  - Persisted deep-research planning integrated into the runtime coordinator
  - Stable thread metadata and checkpoint-aware resume helpers
  - Persisted status snapshots and structured logging for deep-research stages
affects: [api, runtime, testing]
tech-stack:
  added: [deepagents, postgres-backed artifacts, structured runtime logging]
  patterns: [thin runtime coordinator, explicit supervisor/resume/logging modules, required persistence env]
key-files:
  created:
    - backend/agent/deep_agents/supervisor.py
    - backend/agent/deep_agents/resume.py
    - backend/agent/deep_agents/logging.py
    - backend/tests/agent/test_deep_agent_resume.py
    - backend/tests/agent/test_deep_agent_logging.py
  modified:
    - backend/agent/deep_research_runtime.py
    - backend/agent/schemas/deep_research.py
    - backend/api/services/agent_run.py
    - backend/tests/agent/test_deep_research_runtime.py
    - backend/tests/api/test_agent_run_service.py
    - backend/tests/conftest.py
    - backend/tests/test_startup_settings.py
key-decisions:
  - "Kept deep-research orchestration in a thin coordinator and moved persistence behavior into supervisor, resume, and logging modules."
  - "Made thread identifiers stable and derived from run ids so queue-time metadata can anchor checkpoint resume."
  - "Preserved `DEEP_RESEARCH_DATABASE_URL` as a required setting and updated the test harness instead of weakening the contract."
patterns-established:
  - "Deep-research stages persist status artifacts and structured logs through a dedicated helper."
  - "Resume rehydrates job stage and subquestions from persisted status plus checkpoint presence, not process-local memory."
requirements-completed: [PLAN-01, PLAN-02, PLAN-03, PLAN-04]
duration: 17min
completed: 2026-03-24
---

# Phase 3: Deep Agents Persistence Backbone Summary

**Persistent deep-research planning, checkpoint-aware resume metadata, and inspectable stage logging wired into the runtime and API path**

## Performance

- **Duration:** 17 min
- **Started:** 2026-03-24T06:32:01Z
- **Completed:** 2026-03-24T06:49:03Z
- **Tasks:** 3
- **Files modified:** 12

## Accomplishments

- Replaced the old in-memory-only planning handoff with a supervisor-backed plan persistence flow that writes plan and subquestion artifacts before wave execution.
- Added stable `thread_id` handling through deep-research startup plus checkpoint-aware resume helpers for restoring persisted state.
- Mirrored deep-research stages into persisted status artifacts and structured log payloads, then verified the whole backend suite under Python 3.12.

## Task Commits

1. **Task 1: Replace placeholder deep-research planning state with persisted supervisor artifacts** - `d80fd31` (`feat`)
2. **Task 2: Add checkpoint resume and stable thread metadata through the API entry path** - `098259a` (`feat`)
3. **Task 3: Mirror stage transitions into persisted status artifacts and structured logs** - `c159341` (`feat`)
4. **Verification support: cover required deep research database setting** - `dbd9f5f` (`test`)

## Files Created/Modified

- `backend/agent/deep_research_runtime.py` - coordinates persisted planning, resume restoration, stage logging, and final answer artifact writes.
- `backend/agent/deep_agents/supervisor.py` - builds the Deep Agents supervisor entrypoint and persists canonical plan artifacts.
- `backend/agent/deep_agents/resume.py` - restores run state from persisted status and checkpoint presence using stable thread ids.
- `backend/agent/deep_agents/logging.py` - writes persisted status snapshots and emits structured runtime log payloads.
- `backend/api/services/agent_run.py` - passes stable deep-research thread metadata from the API service into startup.
- `backend/tests/agent/test_deep_research_runtime.py` - proves plan persistence happens before wave execution.
- `backend/tests/agent/test_deep_agent_resume.py` - proves resume restores persisted state instead of resetting it.
- `backend/tests/agent/test_deep_agent_logging.py` - proves status artifact content and structured log payload keys.
- `backend/tests/test_startup_settings.py` - covers the required deep-research database setting at startup.

## Decisions Made

- Used the runtime’s existing synchronous entrypoints and wrapped Postgres store/checkpointer usage behind dedicated modules instead of spreading async persistence details through the API layer.
- Stored the canonical plan as markdown bullets derived from the resolved subquestions so the persisted plan artifact is human-readable and deterministic in tests.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Backend route/startup tests needed the new required database setting**
- **Found during:** Task 3 verification
- **Issue:** Route and startup tests failed because `DEEP_RESEARCH_DATABASE_URL` became required and existing test fixtures only set the OpenAI and Serper keys.
- **Fix:** Added an autouse backend test fixture for the database URL and explicit startup coverage that asserts the new setting is required.
- **Files modified:** `backend/tests/conftest.py`, `backend/tests/test_startup_settings.py`
- **Verification:** `pytest tests/api/test_agent_run_service.py tests/api/test_agent_run_route.py tests/test_startup_settings.py tests/test_healthz.py -q`, `pytest tests -q`
- **Committed in:** `dbd9f5f`

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** No scope creep. The deviation was required to keep the strengthened runtime contract testable across the existing backend suite.

## Issues Encountered

- Route-level startup began failing as soon as the database URL moved from implicit to required, which surfaced an incomplete test harness rather than a production runtime problem.

## User Setup Required

None - no external service configuration required beyond the compose-managed Postgres service already added in plan 01.

## Next Phase Readiness

- Deep-research runs now persist planning artifacts before fan-out, carry stable thread ids, and expose progress through persisted status snapshots and structured logs.
- The backend container has been rebuilt with the new dependencies and is healthy alongside Postgres, so the next phase can build on a live persistence-enabled runtime.

---
*Phase: 03-deep-agents-persistence-backbone*
*Completed: 2026-03-24*
