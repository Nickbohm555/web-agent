---
phase: 03-deep-agents-persistence-backbone
plan: 01
subsystem: infra
tags: [deepagents, postgres, langgraph, persistence, testing]
requires: []
provides:
  - Deep Agents persistence dependencies and Postgres runtime wiring
  - Composite backend routing for durable run and plan artifacts
  - Typed persisted plan and status schemas with wave-0 routing tests
affects: [deep-research-runtime, api, testing]
tech-stack:
  added: [deepagents, langgraph-checkpoint-postgres, psycopg]
  patterns: [explicit persistence modules, run-scoped artifact namespaces, dockerized Postgres dependency]
key-files:
  created:
    - backend/agent/deep_agents/persistence/backend_factory.py
    - backend/agent/deep_agents/persistence/checkpointer.py
    - backend/agent/deep_agents/persistence/store.py
    - backend/agent/deep_agents/persistence/artifacts.py
    - backend/agent/deep_agents/schemas/persisted_plan.py
    - backend/agent/deep_agents/schemas/persisted_status.py
    - backend/tests/agent/test_deep_agent_persistence.py
  modified:
    - backend/requirements.txt
    - backend/app/config.py
    - docker-compose.yml
    - backend/tests/conftest.py
key-decisions:
  - "Pinned the backend to the official Deep Agents and Postgres persistence stack required by Phase 3."
  - "Kept persistence helpers in small deep_agents modules instead of extending the legacy in-memory runtime files."
  - "Scoped durable artifact backends by run_id via explicit namespace lambdas."
patterns-established:
  - "Deep-research persistence modules expose direct helpers rather than generic runner abstractions."
  - "Durable artifacts live under /runs/{run_id}/... and route through StoreBackend while scratch remains in StateBackend."
requirements-completed: [PLAN-01, PLAN-02, PLAN-03]
duration: 20min
completed: 2026-03-24
---

# Phase 3: Deep Agents Persistence Backbone Summary

**Deep Agents Postgres persistence wiring with run-scoped artifact routing, typed persisted artifacts, and wave-0 persistence coverage**

## Performance

- **Duration:** 20 min
- **Started:** 2026-03-24T06:12:00Z
- **Completed:** 2026-03-24T06:32:01Z
- **Tasks:** 3
- **Files modified:** 13

## Accomplishments

- Pinned the backend to the Deep Agents, LangGraph checkpoint, and psycopg versions required for durable persistence.
- Added focused persistence modules for backend routing, Postgres store/checkpointer setup, and durable artifact path construction.
- Added wave-0 tests that prove artifact paths, store-backed routing, and run-scoped namespaces before runtime integration work.

## Task Commits

1. **Task 1: Align backend dependencies and Postgres runtime configuration** - `a70c056` (`chore`)
2. **Task 2: Add atomic persistence modules and typed artifact schemas** - `2329ee9` (`feat`)
3. **Task 3: Add Wave 0 persistence coverage and Postgres-aware fixtures** - `fbdbe49` (`test`)

## Files Created/Modified

- `backend/requirements.txt` - pins the Deep Agents and Postgres persistence stack.
- `backend/app/config.py` - adds deep-research database and namespace settings.
- `docker-compose.yml` - provisions Postgres and wires backend startup to a healthy database.
- `backend/agent/deep_agents/persistence/backend_factory.py` - builds the composite backend with explicit store routes.
- `backend/agent/deep_agents/persistence/checkpointer.py` - opens and initializes the async Postgres saver.
- `backend/agent/deep_agents/persistence/store.py` - opens and initializes the async Postgres store.
- `backend/agent/deep_agents/persistence/artifacts.py` - defines canonical durable artifact paths and namespace helpers.
- `backend/agent/deep_agents/schemas/persisted_plan.py` - types persisted plan artifacts.
- `backend/agent/deep_agents/schemas/persisted_status.py` - types persisted status artifacts.
- `backend/tests/agent/test_deep_agent_persistence.py` - verifies artifact layout, route wiring, and namespace scoping.

## Decisions Made

- Used Python 3.12 container verification because the host interpreter is Python 3.9 and cannot install the required Deep Agents packages.
- Kept namespace routing keyed only by `run_id` so the persistence backbone stays simple and consistent for phase 2 runtime integration.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Verified Deep Agents package resolution inside Python 3.12 instead of the host interpreter**
- **Found during:** Task 1 (Align backend dependencies and Postgres runtime configuration)
- **Issue:** Host Python 3.9 could not resolve `deepagents==0.4.12`, which initially looked like a missing package version.
- **Fix:** Re-ran dependency validation in a Python 3.12 Docker container, which matches the backend runtime and confirmed the pinned versions install correctly.
- **Files modified:** None
- **Verification:** `docker run --rm python:3.12-slim ... pip install -q deepagents==0.4.12 ...`
- **Committed in:** `a70c056` (task context only; no file changes required)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** No scope change. The deviation only corrected the validation environment so the planned dependency pins could be implemented safely.

## Issues Encountered

- Host-local test execution is not reliable for this phase because the installed interpreter is Python 3.9 while the backend runtime is Python 3.12.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The runtime now has dependency, config, and persistence module seams ready for plan persistence, resume, and status logging integration.
- Wave 2 can build on explicit artifact paths, store/checkpointer factories, and run-scoped backend routing without changing the persistence foundation.

---
*Phase: 03-deep-agents-persistence-backbone*
*Completed: 2026-03-24*
