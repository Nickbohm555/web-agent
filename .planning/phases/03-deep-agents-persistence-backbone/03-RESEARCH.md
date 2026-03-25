# Phase 3: Deep Agents Persistence Backbone - Research

**Researched:** 2026-03-24
**Domain:** Deep Agents persistence, LangGraph checkpointing, Postgres-backed artifact storage
**Confidence:** MEDIUM

## Summary

Phase 3 should not extend [`backend/agent/deep_research_store.py`](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/agent/deep_research_store.py). That module is process-local and cannot satisfy durable plan artifacts, resumable threads, or inspectable progress.

The target shape for this phase is:

- `create_deep_agent(...)`
- `AsyncPostgresSaver`
- `AsyncPostgresStore`
- `CompositeBackend`
- `StateBackend` for thread-local scratch data
- `StoreBackend` for durable run artifacts with explicit `namespace=lambda ctx: ...`

The canonical durable artifacts for this phase are:

- `/runs/{run_id}/plan.md`
- `/runs/{run_id}/subquestions.json`
- `/runs/{run_id}/status.json`
- `/runs/{run_id}/final_answer.md`

Structured logs should mirror those artifacts and include exact keys `run_id`, `thread_id`, `stage`, and `artifact_path` so progress remains inspectable without a new frontend surface.

## Phase Requirements

| ID | Planning implication |
|----|----------------------|
| `PLAN-01` | Persist a high-level plan artifact before fan-out begins |
| `PLAN-02` | Read persisted plan state back to derive subquestions |
| `PLAN-03` | Resume with stable `thread_id` through Postgres-backed checkpoints |
| `PLAN-04` | Keep progress inspectable through persisted artifacts and structured logging |

## Key Constraints

- The backend Docker image already runs Python 3.12, so the container runtime is compatible with current Deep Agents packages.
- Current pinned backend dependencies lag the modern Deep Agents stack, so dependency alignment must be planned explicitly.
- `StoreBackend` should always use an explicit namespace function; implicit namespace behavior is deprecated.
- Repo guidance in [`AGENTS.md`](/Users/nickbohm/Desktop/Tinkering/web-agent/AGENTS.md) requires small runtime modules rather than growing `backend/agent/deep_research_runtime.py` into a monolith.

## Recommended Module Split

```text
backend/agent/deep_agents/
  persistence/
    backend_factory.py
    checkpointer.py
    store.py
    artifacts.py
  schemas/
    persisted_plan.py
    persisted_status.py
  supervisor.py
  resume.py
  logging.py
```

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | `pytest` for backend, `vitest 4.1.0` for frontend/server contracts |
| Config file | none |
| Quick run command | `pytest backend/tests/agent/test_deep_research_runtime.py backend/tests/api/test_agent_run_service.py -q` |
| Full suite command | `pytest backend/tests -q && npm test` |

### Phase Requirements → Test Map

| Req ID | Behavior | Automated Command | File Exists? |
|--------|----------|-------------------|-------------|
| `PLAN-01` | Persist plan artifact before fan-out | `pytest backend/tests/agent/test_deep_agent_persistence.py -q` | ❌ Wave 0 |
| `PLAN-02` | Derive subquestions from persisted plan artifact | `pytest backend/tests/agent/test_deep_agent_persistence.py -q` | ❌ Wave 0 |
| `PLAN-03` | Resume from Postgres checkpoint plus artifacts | `pytest backend/tests/agent/test_deep_agent_resume.py -q` | ❌ Wave 0 |
| `PLAN-04` | Inspect progress through persisted artifacts and logging | `pytest backend/tests/api/test_agent_run_route.py -q && npm test -- run-history.integration.test.ts` | ⚠️ Partial |

## Sources

- https://docs.langchain.com/oss/python/deepagents/overview
- https://docs.langchain.com/oss/python/deepagents/backends
- https://pypi.org/project/langgraph-checkpoint-postgres/
- [`backend/agent/deep_research_runtime.py`](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/agent/deep_research_runtime.py)
- [`backend/agent/deep_research_store.py`](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/agent/deep_research_store.py)
- [`backend/requirements.txt`](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/requirements.txt)

## Research Date

- Research date: 2026-03-24
- Valid until: 2026-03-31
