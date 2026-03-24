# Phase 3: Deep Agents Persistence Backbone - Research

**Researched:** 2026-03-24
**Domain:** Deep Agents persistence, LangGraph checkpointing, Postgres-backed artifact storage
**Confidence:** MEDIUM

## User Constraints

No phase-specific `*-CONTEXT.md` exists in `.planning/phases/03-deep-agents-persistence-backbone`.

Operational constraints inferred from `.planning/STATE.md`, `.planning/ROADMAP.md`, and the phase prompt:

- Use Deep Agents backends for planning artifacts.
- Use `langgraph-checkpoint-postgres` for durable thread resume.
- Keep inspectable progress in persisted artifacts and logging without requiring new frontend work.
- Preserve explicit runtime seams and small task-focused Python modules; do not hide runtime flow behind generic runners.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PLAN-01 | User can have each `deep_research` run create a persistent high-level research plan before parallel research begins. | Use Deep Agents built-in planning plus a backend factory that routes durable plan files into `StoreBackend` namespaces keyed by run/thread. |
| PLAN-02 | User can have the orchestrator derive subquestions or research angles from that persistent plan. | Persist the canonical plan and derived subquestion artifacts in the Deep Agents filesystem surface, then have the supervisor read those files back rather than relying on ad hoc Python-only state. |
| PLAN-03 | User can resume an interrupted `deep_research` run from persisted workflow state backed by LangGraph checkpointing and Postgres. | Compile `create_deep_agent(...)` with `AsyncPostgresSaver` and a stable `thread_id`; call `setup()` once during bootstrap. |
| PLAN-04 | User can inspect deep-research progress indirectly through persisted artifacts and logging without requiring a new frontend feature set. | Persist status snapshots and plan/result files in Postgres-backed storage, and emit structured logs keyed by `run_id`, `thread_id`, and artifact paths. |
</phase_requirements>

## Summary

Phase 3 should not extend the current `InMemoryDeepResearchStore`. That store is only a placeholder and cannot satisfy persisted plan artifacts, resumable threads, or inspectable progress. The correct shape is a compiled Deep Agents graph created with `create_deep_agent(...)`, an explicit Deep Agents backend factory for file-like artifacts, and `AsyncPostgresSaver` for checkpointed LangGraph thread state.

The important architectural split is thread-local versus cross-thread persistence. Use `StateBackend` for ephemeral scratch files that should resume inside one thread through checkpointing. Use `StoreBackend` for durable artifacts that must survive across restarts and be inspectable later. Use `CompositeBackend` so the agent sees one filesystem surface while the runtime routes `/runs/...` or `/plans/...` paths into durable Postgres-backed storage.

There is also a hard sequencing constraint: the current repo pins `langchain==0.3.27` and `langgraph==0.6.11`, while current `deepagents` requires Python `>=3.11` and `langchain>=1.2.11`. The backend Docker image is already Python 3.12, so the container target is acceptable, but Phase 3 planning must treat dependency alignment as prerequisite work if Phase 2 has not already upgraded the runtime.

**Primary recommendation:** Plan Phase 3 around one async persistence spine: `create_deep_agent(...)` + `AsyncPostgresSaver` + `AsyncPostgresStore` + `CompositeBackend(StateBackend, StoreBackend)` with explicit run-scoped namespaces and persisted status artifacts.

## Standard Stack

### Core

| Library | Verified Version | Published | Purpose | Why Standard |
|---------|------------------|-----------|---------|--------------|
| `deepagents` | `0.4.12` | 2026-03-20 | Deep Agents harness and backend abstractions | Official Deep Agents package; exposes `create_deep_agent`, `StateBackend`, `StoreBackend`, and `CompositeBackend`. |
| `langgraph-checkpoint-postgres` | `3.0.5` | 2026-03-18 | Durable LangGraph checkpointing in Postgres | Official Postgres saver package; provides `PostgresSaver` and `AsyncPostgresSaver`. |
| `langgraph` | `1.1.3` | 2026-03-18 | Runtime graph/checkpoint/store primitives | Current LangGraph line paired with modern Deep Agents. |
| `langchain` | `1.2.13` | 2026-03-19 | Agent runtime used by Deep Agents | Required by current `deepagents`; current repo is behind this line. |
| `psycopg` | `3.3.3` | 2026-02-18 | Postgres driver | Required by official Postgres saver/store implementations. |

### Supporting

| Library | Verified Version | Published | Purpose | When to Use |
|---------|------------------|-----------|---------|-------------|
| `langchain-openai` | `1.1.12` | 2026-03-23 | OpenAI model integration | If this repo keeps OpenAI as the supervisor/subagent model provider. |
| `psycopg-pool` | bundled requirement in `langgraph-checkpoint-postgres 3.0.5` | 2026-03-18 | Connection pooling | Use when backend concurrency grows beyond a single saver/store connection. |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `CompositeBackend(default=StateBackend, routes=StoreBackend)` | `FilesystemBackend` | Reject for HTTP/server persistence. Official docs warn `FilesystemBackend` is inappropriate for web servers. |
| `AsyncPostgresSaver` | `PostgresSaver` | Sync saver is acceptable for sync graphs, but this backend should prefer async wiring to match FastAPI/background execution. |
| `StoreBackend` for durable artifacts | Custom ORM tables | Reject for this phase. LangGraph store already gives namespaced durable blobs and file-like semantics Deep Agents expects. |

**Installation:**

```bash
pip install "deepagents==0.4.12" "langgraph-checkpoint-postgres==3.0.5" "langchain==1.2.13" "langgraph==1.1.3" "langchain-openai==1.1.12" "psycopg[binary]==3.3.3"
```

**Version verification:**

```bash
python - <<'PY'
import json, urllib.request
for name in ["deepagents", "langgraph-checkpoint-postgres", "langgraph", "langchain", "langchain-openai", "psycopg"]:
    with urllib.request.urlopen(f"https://pypi.org/pypi/{name}/json") as resp:
        data = json.load(resp)
    version = data["info"]["version"]
    published = data["releases"][version][0]["upload_time_iso_8601"]
    print(name, version, published)
PY
```

## Architecture Patterns

### Recommended Project Structure

```text
backend/
├── agent/
│   ├── deep_agents/
│   │   ├── persistence/
│   │   │   ├── backend_factory.py      # CompositeBackend and namespace wiring
│   │   │   ├── checkpointer.py         # AsyncPostgresSaver lifecycle
│   │   │   ├── store.py                # AsyncPostgresStore lifecycle
│   │   │   └── artifacts.py            # plan/status/result file conventions
│   │   ├── schemas/
│   │   │   ├── persisted_plan.py
│   │   │   └── persisted_status.py
│   │   ├── supervisor.py               # create_deep_agent(...) assembly
│   │   └── resume.py                   # thread/run resume entrypoints
│   └── ...
└── tests/
    └── agent/
        ├── test_deep_agent_persistence.py
        └── test_deep_agent_resume.py
```

### Pattern 1: One Explicit Persistence Spine

**What:** Build one async assembly path that creates the Postgres store, Postgres checkpointer, backend factory, and compiled Deep Agent graph together.

**When to use:** Always for server-side deep-research runs.

**Example:**

```python
from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres.aio import AsyncPostgresStore


def build_backend(runtime, run_id: str):
    return CompositeBackend(
        default=StateBackend(runtime),
        routes={
            "/runs/": StoreBackend(
                runtime,
                namespace=lambda ctx: ("deep_research", run_id),
            ),
        },
    )


async def build_supervisor(model, tools, db_uri: str, run_id: str):
    store_cm = AsyncPostgresStore.from_conn_string(db_uri)
    saver_cm = AsyncPostgresSaver.from_conn_string(db_uri)
    store = await store_cm.__aenter__()
    saver = await saver_cm.__aenter__()
    await store.setup()
    await saver.setup()
    return create_deep_agent(
        model=model,
        tools=tools,
        backend=lambda runtime: build_backend(runtime, run_id),
        store=store,
        checkpointer=saver,
    )
```

Source: official Deep Agents `create_deep_agent(...)` API and official LangGraph Postgres saver/store implementations.

### Pattern 2: Persist Canonical Artifacts as Files, Not Only Python Models

**What:** Treat the plan, derived subquestions, and run status as first-class Deep Agents files in durable storage.

**When to use:** For all planner outputs and inspectable progress snapshots.

**Example paths:**

```text
/runs/{run_id}/plan.md
/runs/{run_id}/subquestions.json
/runs/{run_id}/status.json
/runs/{run_id}/final_answer.md
```

This keeps the persisted plan inspectable through backend tooling, direct store reads, or future frontend surfaces without changing the top-level API envelope.

### Pattern 3: Stable Namespace Boundaries

**What:** Use explicit namespace factories for `StoreBackend`; do not rely on deprecated legacy assistant ID detection.

**When to use:** Every `StoreBackend` instantiation.

**Example:**

```python
StoreBackend(
    runtime,
    namespace=lambda ctx: ("deep_research", ctx.runtime.context.run_id),
)
```

This prevents cross-run artifact collisions and aligns with the package’s deprecation path.

### Pattern 4: Structured Progress Logging Mirrors Artifact Writes

**What:** Every stage transition should both update `/runs/{run_id}/status.json` and emit a structured application log entry with the same identifiers.

**When to use:** Planning start, plan persisted, resume start, checkpoint resume, synthesis start, completion, failure.

This satisfies PLAN-04 without frontend work. Existing UI history can remain optional; persisted inspectability must not depend on the frontend process memory store in [`src/frontend/run-history/store.ts`](/Users/nickbohm/Desktop/Tinkering/web-agent/src/frontend/run-history/store.ts).

### Anti-Patterns to Avoid

- **Extending `InMemoryDeepResearchStore`:** It cannot deliver durable resume or inspectable artifacts.
- **Using `FilesystemBackend` in the HTTP backend:** Official docs explicitly warn against it for web servers.
- **Keeping plan state only inside Python dataclasses/Pydantic models:** The plan must also exist as persisted backend artifacts.
- **Implicit namespace scoping:** `StoreBackend` without explicit `namespace=` is already deprecated.
- **Treating frontend run history as the source of truth:** Current history storage is in-memory in the frontend process, so it is not persistence.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Thread checkpoint persistence | Custom checkpoint tables and serializers | `AsyncPostgresSaver` | Official saver already handles checkpoint schema, writes, listing, and resume by `thread_id`. |
| Durable artifact storage | Ad hoc JSON blobs in custom tables | `AsyncPostgresStore` + `StoreBackend` | Gives namespaced storage that Deep Agents backends already know how to read/write. |
| Mixed ephemeral/durable filesystem routing | Custom path router | `CompositeBackend` | Built for route-prefix dispatch such as `/runs/` to durable storage and scratch paths to state. |
| Per-run scoping | Manual string concatenation for keys | `StoreBackend(namespace=lambda ctx: ...)` | Centralizes isolation and avoids deprecated implicit metadata behavior. |
| Progress visibility | New frontend UI | Persisted status files + structured logs + existing event contracts | Meets PLAN-04 with lower scope and less coordination risk. |

**Key insight:** The value of Deep Agents here is not only the agent loop. It is the contract between graph state, filesystem-like artifacts, and subagent tooling. Replacing that with custom persistence code would recreate edge cases the official backends already solve.

## Common Pitfalls

### Pitfall 1: Dependency Mismatch With Current Repo

**What goes wrong:** Planning assumes Deep Agents can be dropped into the current backend without upgrading runtime dependencies.

**Why it happens:** The repo currently pins `langchain==0.3.27` and `langgraph==0.6.11`, while current `deepagents` requires `langchain>=1.2.11` and Python `>=3.11`.

**How to avoid:** Put dependency alignment in Wave 0 for this phase unless Phase 2 already completed it.

**Warning signs:** Import failures around `langchain.agents.create_agent`, missing Deep Agents APIs, or incompatible type signatures.

### Pitfall 2: Forgetting `setup()` on Saver/Store

**What goes wrong:** Resume or artifact reads fail because the database tables were never initialized.

**Why it happens:** Both official Postgres implementations require explicit first-run setup.

**How to avoid:** Run `await saver.setup()` and `await store.setup()` in bootstrap guarded by idempotent startup logic.

**Warning signs:** Missing table errors or empty persistence after apparently successful writes.

### Pitfall 3: Missing `autocommit=True` / `dict_row`

**What goes wrong:** Manual Postgres connections fail or `.setup()` does not persist.

**Why it happens:** The saver/store implementations access rows by column name and expect committed DDL.

**How to avoid:** Prefer `.from_conn_string(...)`. If manually wiring connections, always pass `autocommit=True` and `row_factory=dict_row`.

**Warning signs:** `TypeError` on tuple indexing or migrations that appear to run but do not stick.

### Pitfall 4: Using Deprecated Store Namespace Fallback

**What goes wrong:** Artifacts bleed across runs or later break on Deep Agents upgrades.

**Why it happens:** `StoreBackend` can still infer namespace from metadata, but that path is deprecated and scheduled to become mandatory explicit configuration.

**How to avoid:** Always pass `namespace=lambda ctx: (...)`.

**Warning signs:** Warnings about deprecated `StoreBackend` usage or unexpected cross-run file visibility.

### Pitfall 5: Conflating Checkpoints With Durable Artifacts

**What goes wrong:** Resume works, but plan inspection does not, or vice versa.

**Why it happens:** Checkpoints persist graph state; they are not a substitute for durable file artifacts intended for human inspection.

**How to avoid:** Persist checkpoints and file artifacts separately but keyed by the same `run_id`/`thread_id`.

**Warning signs:** A run resumes, yet no readable `plan.md` or `status.json` exists.

## Code Examples

Verified patterns from official sources:

### Async Postgres Checkpointer

```python
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

async with AsyncPostgresSaver.from_conn_string(DB_URI) as saver:
    await saver.setup()
    config = {"configurable": {"thread_id": run_id, "checkpoint_ns": ""}}
    checkpoint = await saver.aget(config)
```

Source: https://pypi.org/project/langgraph-checkpoint-postgres/

### Route Durable Artifacts Into Postgres Storage

```python
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend

backend = lambda runtime: CompositeBackend(
    default=StateBackend(runtime),
    routes={
        "/runs/": StoreBackend(
            runtime,
            namespace=lambda ctx: ("deep_research", run_id),
        )
    },
)
```

Source: official Deep Agents backend APIs in `deepagents` package.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Keep deep-research state in an in-memory Python store | Compile a Deep Agent graph with Postgres saver/store | Current official Deep Agents / LangGraph line as of 2026-03 | Enables restart-safe resume and durable artifacts. |
| Use local filesystem semantics for server persistence | Use `StateBackend` and `StoreBackend` under `CompositeBackend` | Current Deep Agents backend guidance | Safer server-side persistence and better path routing. |
| Let `StoreBackend` infer namespace from metadata | Pass explicit namespace factories | Deprecated in current `deepagents` source, becoming required in `0.5.0` | Planner should schedule explicit namespace wiring now. |

**Deprecated/outdated:**

- `backend/agent/deep_research_store.py` as the persistence backbone for deep research.
- Treating frontend in-memory run history as persistence.

## Open Questions

1. **Will Phase 2 already have `create_deep_agent(...)` in place before this phase starts?**
   - What we know: Roadmap says yes; current repo code says no.
   - What's unclear: Whether dependency upgrades land in Phase 2 or must be pulled into Phase 3.
   - Recommendation: Planner should add an explicit dependency/runtime alignment task if Phase 2 deliverables are not already merged.

2. **What is the canonical database configuration surface?**
   - What we know: There is no current backend Postgres config, env var, or service in the repo.
   - What's unclear: Whether to add a dedicated Postgres service in `docker-compose.yml` this phase or rely on an external database.
   - Recommendation: Decide this in planning up front because it affects Docker, settings, tests, and local developer bootstrapping.

3. **How should persisted artifacts be exposed operationally?**
   - What we know: Existing frontend history endpoints are separate and ephemeral.
   - What's unclear: Whether Phase 3 needs only logs plus direct store inspection, or a lightweight backend read endpoint for artifacts.
   - Recommendation: Keep artifact write format stable now (`plan.md`, `status.json`, etc.), and defer any new read API unless planning proves it is required for UAT.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | `pytest` for backend, `vitest 4.1.0` for frontend/server contracts |
| Config file | none |
| Quick run command | `pytest backend/tests/agent/test_deep_research_runtime.py backend/tests/api/test_agent_run_service.py -q` |
| Full suite command | `pytest backend/tests -q && npm test` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PLAN-01 | Persist high-level research plan as durable artifact before fan-out | unit/integration | `pytest backend/tests/agent/test_deep_agent_persistence.py -q` | ❌ Wave 0 |
| PLAN-02 | Derive subquestions from persisted plan artifact | unit/integration | `pytest backend/tests/agent/test_deep_agent_persistence.py -q` | ❌ Wave 0 |
| PLAN-03 | Resume interrupted run from Postgres checkpoint + artifacts | integration | `pytest backend/tests/agent/test_deep_agent_resume.py -q` | ❌ Wave 0 |
| PLAN-04 | Inspect progress indirectly through persisted artifacts/logging | integration/contract | `pytest backend/tests/api/test_agent_run_route.py -q && npm test -- run-history.integration.test.ts` | ⚠️ Partial |

### Sampling Rate

- **Per task commit:** `pytest backend/tests/agent/test_deep_research_runtime.py backend/tests/api/test_agent_run_service.py -q`
- **Per wave merge:** `pytest backend/tests -q`
- **Phase gate:** `pytest backend/tests -q && npm test`

### Wave 0 Gaps

- [ ] `backend/tests/agent/test_deep_agent_persistence.py` — durable plan artifact creation and namespace routing
- [ ] `backend/tests/agent/test_deep_agent_resume.py` — checkpoint resume with stable `thread_id`
- [ ] `backend/tests/agent/test_deep_agent_logging.py` — structured progress logging and status artifact updates
- [ ] Postgres-backed test fixture in [`backend/tests/conftest.py`](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/tests/conftest.py) or dedicated helper
- [ ] Docker/test env for Postgres if planner chooses compose-managed local DB

## Sources

### Primary (HIGH confidence)

- https://docs.langchain.com/oss/python/deepagents/overview - verified `create_deep_agent(...)` is the official Deep Agents entrypoint and that Deep Agents are built on LangGraph.
- https://github.com/langchain-ai/deepagents/blob/main/deepagents/graph.py - verified `create_deep_agent(...)` accepts `checkpointer`, `store`, and `backend`.
- https://github.com/langchain-ai/deepagents/blob/main/deepagents/backends/state.py - verified `StateBackend` is thread-local and checkpoint-backed.
- https://github.com/langchain-ai/deepagents/blob/main/deepagents/backends/store.py - verified `StoreBackend` is persistent, namespace-driven, and explicit namespace usage is the forward path.
- https://github.com/langchain-ai/deepagents/blob/main/deepagents/backends/composite.py - verified route-prefix backend composition.
- https://pypi.org/project/langgraph-checkpoint-postgres/ - verified saver usage requirements, `setup()`, and connection requirements.
- https://github.com/langchain-ai/langgraph/blob/main/libs/checkpoint-postgres/langgraph/checkpoint/postgres/aio.py - verified `AsyncPostgresSaver.from_conn_string(...)`.
- https://github.com/langchain-ai/langgraph/blob/main/libs/checkpoint-postgres/langgraph/store/postgres/aio.py - verified `AsyncPostgresStore.from_conn_string(...)` and `setup()`.
- https://pypi.org/pypi/deepagents/json - verified current package version and publish date.
- https://pypi.org/pypi/langgraph-checkpoint-postgres/json - verified current package version and publish date.
- https://pypi.org/pypi/langgraph/json - verified current package version and publish date.
- https://pypi.org/pypi/langchain/json - verified current package version and publish date.
- https://pypi.org/pypi/langchain-openai/json - verified current package version and publish date.
- https://pypi.org/pypi/psycopg/json - verified current package version and publish date.

### Secondary (MEDIUM confidence)

- [`backend/agent/deep_research_runtime.py`](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/agent/deep_research_runtime.py) - current placeholder orchestration shape to replace.
- [`backend/agent/deep_research_store.py`](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/agent/deep_research_store.py) - current in-memory persistence limitation.
- [`backend/requirements.txt`](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/requirements.txt) - current dependency mismatch against modern Deep Agents stack.
- [`src/frontend/run-history/store.ts`](/Users/nickbohm/Desktop/Tinkering/web-agent/src/frontend/run-history/store.ts) - current run-history persistence is in-memory and not durable.
- [`src/frontend/routes/runs.ts`](/Users/nickbohm/Desktop/Tinkering/web-agent/src/frontend/routes/runs.ts) - existing progress event contracts that can remain unchanged.

### Tertiary (LOW confidence)

- None.

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH - official package metadata and source code were verified on 2026-03-24.
- Architecture: MEDIUM - official APIs are clear, but exact repo integration depends on Phase 2 landing and database ownership decisions.
- Pitfalls: HIGH - dependency constraints, setup requirements, namespace deprecation, and server-backend warnings are explicitly documented in official sources.

**Research date:** 2026-03-24
**Valid until:** 2026-03-31
