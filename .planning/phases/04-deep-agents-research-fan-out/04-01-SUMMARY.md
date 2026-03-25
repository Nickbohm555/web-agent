---
phase: 04-deep-agents-research-fan-out
plan: 01
subsystem: api
tags: [deepagents, langchain, retrieval, pydantic, pytest]
requires:
  - phase: 03
    provides: persisted deep-research lifecycle and inspectable planning artifacts
provides:
  - typed subagent assignment, result, and artifact models
  - shared Deep Agents retrieval tools exposing web_search and open_url
  - supervisor and research-subagent factories for fan-out wiring
affects: [deep_research_runtime, deep_research_execution, phase-04-plan-02]
tech-stack:
  added: []
  patterns: [direct retrieval-tool injection, typed subagent evidence contracts]
key-files:
  created:
    - backend/tests/agent/test_deep_research_subagents.py
    - backend/agent/schemas/deep_research_subagent.py
    - backend/agent/deep_research_retrieval_tools.py
    - backend/agent/deep_research_subagents.py
    - backend/agent/deep_research_supervisor.py
  modified: []
key-decisions:
  - "Keep Deep Agents imports lazy inside the supervisor factory so local tests can run without the package installed."
  - "Expose open_url as a thin wrapper around the existing web_crawl pipeline to preserve retrieval behavior while matching the roadmap contract."
patterns-established:
  - "Deep-research fan-out modules stay split by contract, tools, subagent spec, and supervisor wiring."
  - "Research subagents receive explicit retrieval-tool injection instead of inheriting tools implicitly."
requirements-completed: [RSCH-01, RSCH-02]
duration: 6min
completed: 2026-03-24
---

# Phase 4: Deep Agents Research Fan-Out Summary

**Deep-research fan-out foundation with typed subagent evidence models, shared retrieval-tool injection, and a supervisor factory ready for runtime wiring**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-24T06:51:22Z
- **Completed:** 2026-03-24T06:56:53Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments
- Added a dedicated pytest module covering Deep Agents compatibility, canonical retrieval-tool names, and supervisor construction.
- Added typed Pydantic subagent contracts plus a shared retrieval-tool builder that exposes `web_search` and `open_url`.
- Added split runtime modules for research-subagent specs and supervisor creation so phase 4 runtime wiring has explicit seams.

## Task Commits

Each task was committed atomically:

1. **Task 1: Create Wave 0 tests and a Deep Agents compatibility gate** - `1a4a8a6` (`test`)
2. **Task 2: Add typed subagent schemas and shared retrieval-tool builders** - `e6f32a8` (`feat`)
3. **Task 3: Create research subagent specs and the Deep Agents supervisor factory** - `787b38d` (`feat`)

## Files Created/Modified
- `backend/tests/agent/test_deep_research_subagents.py` - Focused RSCH-01 and RSCH-02 coverage for compatibility, retrieval, and fan-out.
- `backend/agent/schemas/deep_research_subagent.py` - Typed assignment, result, and artifact contracts for delegated research work.
- `backend/agent/deep_research_retrieval_tools.py` - Direct retrieval-tool factory exposing `web_search` and an `open_url` wrapper over `run_web_crawl`.
- `backend/agent/deep_research_subagents.py` - Concrete `research_subagent` spec builder with injected tools.
- `backend/agent/deep_research_supervisor.py` - Supervisor factory that lazily loads `deepagents.create_deep_agent` and records delegated subquestion count metadata.

## Decisions Made
- Kept the Deep Agents dependency behind a lazy loader so local unit tests can exercise the supervisor builder without requiring package installation.
- Preserved the existing crawler implementation by aliasing it to `open_url` at the Deep Agents boundary instead of rewriting retrieval internals.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The local Python environment does not currently have `deepagents` installed, so the compatibility smoke test skips on import and will hard-fail only once the package is present but missing `create_deep_agent`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 4 plan 02 can now wire real delegated subquestion execution through these foundation modules.
- Runtime progress and artifact persistence remain to be connected in `deep_research_execution.py` and `deep_research_runtime.py`.

## Self-Check: PASSED
