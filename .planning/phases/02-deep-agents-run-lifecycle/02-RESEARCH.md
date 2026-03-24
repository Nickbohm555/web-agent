# Phase 2: Deep Agents Run Lifecycle - Research

**Researched:** 2026-03-24
**Domain:** LangChain Deep Agents run lifecycle, clarification gating, and thread resume
**Confidence:** HIGH

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| DEEP-01 | User can start a `deep_research` run that is executed by an orchestrator agent dedicated to deep research. | Replace the placeholder queue path in `backend/api/services/agent_run.py` with a dedicated Deep Agents service built around `create_deep_agent(...)` and explicit thread-backed invocation. |
| DEEP-02 | User can receive at most one clarifying question at a time when the orchestrator determines more context is needed before research starts. | Add explicit run state for `awaiting_clarification` plus one `pending_clarification` field; gate re-entry until the answer arrives instead of letting multiple unresolved questions accumulate. |
| DEEP-03 | User can resume the same `deep_research` run after answering a clarifying question instead of starting over. | Reuse the same LangGraph `thread_id` on every invoke and persist only minimal app-side status around that thread. |
</phase_requirements>

## Summary

The current `deep_research` backend path is still a placeholder queue. `backend/api/services/agent_run.py` returns `202 queued`, and `backend/agent/deep_research_runtime.py` persists an in-memory `DeepResearchJob` that runs a fake plan/waves/verify pipeline. There is no Deep Agents supervisor, no LangGraph thread identity, no clarification state, and no resume surface. That means the current Phase 2 work is a real runtime replacement, not an incremental toggle.

The official LangChain stack for this phase is now `deepagents` on top of LangGraph checkpoints and thread IDs. Deep Agents are created with `create_deep_agent(...)`; thread continuity is carried through `config={"configurable": {"thread_id": ...}}`; and checkpointing is the mechanism that preserves state across interrupts and follow-up turns. For Phase 2, the minimal viable implementation is an in-memory checkpointer plus a small application-side run record. Durable Postgres checkpointing belongs to Phase 3, but Phase 2 should already shape the code around the same `thread_id` contract so the persistence upgrade is mechanical later.

**Primary recommendation:** Build a thin `deep_research` service around one compiled `create_deep_agent(...)`, use `run_id` as the LangGraph `thread_id`, add explicit `awaiting_clarification` state with exactly one `pending_clarification`, and keep all orchestration split into small backend modules rather than expanding the placeholder runtime files.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `deepagents` | `0.4.12` | Deep Agents supervisor via `create_deep_agent(...)` | Official Deep Agents package with built-in planning, subagents, todo tracking, and filesystem primitives. |
| `langgraph` | `1.1.3` | Thread/checkpoint runtime | Official persistence model for thread resume and interrupts. |
| `langchain` | `1.2.13` | Agent/middleware/model integration layer | Current LangChain 1.x line aligns with current Deep Agents docs and middleware APIs. |
| `langchain-openai` | `1.1.12` | OpenAI chat model integration | Current OpenAI integration package for the LangChain 1.x line. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `langgraph-checkpoint-postgres` | `3.0.5` | Durable checkpoint backend | Phase 3 production persistence; shape Phase 2 code so this drops in later. |
| `pydantic-settings` | `2.8.1` | Settings/env management | Keep backend config typed when adding Deep Agents flags and model settings. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Deep Agents supervisor | Keep custom `deep_research_runtime.py` job pipeline | Faster short-term, but directly conflicts with DEEP-01 and duplicates planning/subagent orchestration Deep Agents already provides. |
| LangGraph thread checkpoints | Custom replay of prior prompt/answer pairs | Simpler on day one, but fragile and redundant once Deep Agents already expects checkpoint-backed thread state. |
| App-side clarification gate | Let the agent freely ask follow-up questions in plain text | Less code, but it does not guarantee the “one outstanding clarification” requirement. |

**Installation:**
```bash
pip install -U deepagents langgraph langchain langchain-openai
```

**Version verification:** Verified against PyPI on 2026-03-24.
- `deepagents 0.4.12` released 2026-03-20
- `langgraph 1.1.3` released 2026-03-18
- `langchain 1.2.13` released 2026-03-19
- `langchain-openai 1.1.12` released 2026-03-23
- `langgraph-checkpoint-postgres 3.0.5` released 2026-03-18

**Compatibility note:** `deepagents` requires Python `>=3.11`. The repo’s backend container already uses Python 3.12 in [backend/Dockerfile](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/Dockerfile), but the local shell on this machine is Python 3.9.13. Do not use the local Python version as the compatibility baseline for this phase.

## Architecture Patterns

### Recommended Project Structure
```text
backend/
├── agent/
│   ├── deep_agents/
│   │   ├── factory.py              # create_deep_agent(...) construction
│   │   ├── invocation.py           # invoke/stream helpers with thread_id config
│   │   ├── clarification.py        # single-question gate + state transitions
│   │   ├── run_state.py            # app-side run record storage helpers
│   │   └── service.py              # direct start/resume entrypoints
│   ├── schemas/
│   │   ├── deep_research_run.py    # backend run-state models
│   │   └── deep_research_events.py # optional streamed event models
│   └── runtime_execution.py        # keep existing quick/agentic routing small
├── api/
│   ├── routes/
│   │   └── agent_run.py            # start endpoint + explicit resume endpoint
│   └── schemas/
│       ├── agent_run.py            # existing request/queued success models
│       └── deep_research_resume.py # resume request/response models
```

### Pattern 1: Thin Service Around One Compiled Deep Agent
**What:** Create a focused service that owns Deep Agents creation and thread-based invocation, instead of extending the placeholder queue job flow.
**When to use:** Immediately for all `deep_research` starts and resumes.
**Example:**
```python
# Source: https://docs.langchain.com/oss/python/deepagents/customization
from deepagents import create_deep_agent
from langgraph.checkpoint.memory import InMemorySaver

checkpointer = InMemorySaver()

deep_research_agent = create_deep_agent(
    model="openai:gpt-5",
    tools=[web_search_tool, open_url_tool],
    checkpointer=checkpointer,
    system_prompt=DEEP_RESEARCH_SYSTEM_PROMPT,
)

result = deep_research_agent.invoke(
    {"messages": [{"role": "user", "content": prompt}]},
    config={"configurable": {"thread_id": run_id}},
)
```

### Pattern 2: Reuse `run_id` as `thread_id`
**What:** Treat the externally visible `run_id` as the LangGraph `thread_id`.
**When to use:** For every Phase 2 deep-research invoke and resume.
**Example:**
```python
# Source: https://docs.langchain.com/oss/python/langgraph/persistence
config = {"configurable": {"thread_id": run_id}}
agent.invoke(inputs, config=config)
```

**Why:** The current API and frontend already revolve around `run_id`. Reusing it avoids adding a second identifier before Phase 3 persistence work. This is an inference from the current repo contracts plus LangGraph’s thread model.

### Pattern 3: App-Side Clarification Gate, Checkpointer for Conversation Memory
**What:** Store exactly one outstanding clarification in app-side run state, but rely on the checkpointer for the actual message history and Deep Agent state.
**When to use:** Before the first research fan-out and on each clarification answer.
**Example:**
```python
class DeepResearchRunState(BaseModel):
    run_id: str
    status: Literal["queued", "awaiting_clarification", "running", "completed", "failed"]
    retrieval_policy: AgentRunRetrievalPolicy
    pending_clarification: str | None = None
    clarification_count: int = 0
```

**Minimal state required in Phase 2:**
- `run_id` / `thread_id`
- API-visible status
- `retrieval_policy`
- `pending_clarification`
- `clarification_count`
- timestamps and terminal error/result metadata

**Not required in app state:** full message history, planner scratchpad, or subagent internal state. The checkpointer should own those.

### Pattern 4: Separate Start and Resume Entrypoints
**What:** Keep new-run and clarification-resume requests on explicit paths or schemas.
**When to use:** When DEEP-03 is implemented.
**Example:**
```text
POST /api/agent/run                  # start new run
POST /api/agent/run/{run_id}/resume  # answer pending clarification
```

**Why:** The current `AgentRunRequest` has no thread/run identifier, so overloading it for continuation would blur validation and routing.

### Anti-Patterns to Avoid
- **Do not extend `backend/agent/deep_research_runtime.py` into a second custom orchestrator:** that duplicates the capability Phase 2 is supposed to adopt from Deep Agents.
- **Do not store conversation history twice:** keep app state minimal and let the checkpointer own thread state.
- **Do not hide runtime dispatch behind generic callable registries:** the repo explicitly prefers direct function paths; keep `start_deep_research_run(...)` and `resume_deep_research_run(...)` as concrete calls.
- **Do not track clarification counters in mutable middleware instance fields:** official docs warn that middleware mutation is unsafe under concurrent subagents and invocations.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Deep research orchestration | Custom planner + subagent scheduler + todo tracker | `create_deep_agent(...)` | Deep Agents already ships planning, subagents, and task decomposition primitives. |
| Thread resume | Manual replay of prior prompts and answers | LangGraph checkpointer + `thread_id` | Checkpoints preserve actual graph state and are the official resume model. |
| In-thread scratch filesystem | Ad hoc dicts or temp files | Deep Agents `StateBackend` | It is already integrated with thread-scoped agent state. |
| Human approval plumbing | Custom pause/resume framework for tool approvals | Built-in HITL middleware later when needed | Official middleware already depends on checkpointers and is the supported pause model. |

**Key insight:** Phase 2 should hand-roll only the app-facing run lifecycle shell: status transitions, one-question enforcement, and API routing. It should not hand-roll the research supervisor itself.

## Common Pitfalls

### Pitfall 1: Python-Version Blindness During Dependency Planning
**What goes wrong:** You think the current stack is only `langchain 0.3.x` because local package tooling hides newer releases.
**Why it happens:** The local shell is Python 3.9.13, which filters out Python 3.10+/3.11+ packages from commands like `pip index`.
**How to avoid:** Treat the backend container as the real runtime baseline; Phase 2 dependency planning must target Python 3.12 from [backend/Dockerfile](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/Dockerfile).
**Warning signs:** Local pip claims `langchain 0.3.28` is latest while PyPI shows `1.2.13`.

### Pitfall 2: Forgetting `thread_id`
**What goes wrong:** Clarification answers start a fresh run instead of continuing the same reasoning state.
**Why it happens:** LangGraph persistence requires `configurable.thread_id` on invocation.
**How to avoid:** Make `run_id` the mandatory thread key in one shared helper and never invoke the Deep Agent without it.
**Warning signs:** Clarification answer loses prior context or cannot resume after an interrupt.

### Pitfall 3: Letting the Agent Ask More Than One Unresolved Question
**What goes wrong:** The model emits multiple clarifying questions or asks a second one before the first is answered.
**Why it happens:** Prompt-only guidance is soft; no app-side state blocks repeated clarifications.
**How to avoid:** Add explicit `awaiting_clarification` status and reject or queue any further progress until the pending answer is supplied.
**Warning signs:** One run has multiple outstanding question prompts or the UI cannot tell which one to answer.

### Pitfall 4: Using Middleware Mutable Instance State
**What goes wrong:** Clarification counters or gating flags drift across threads or concurrent runs.
**Why it happens:** Middleware hooks may run alongside subagents, tools, and concurrent invocations.
**How to avoid:** Put cross-turn state in graph state or app-side run records, not `self.some_counter`.
**Warning signs:** One run’s clarification state bleeds into another run.

### Pitfall 5: Over-scoping Phase 2 Into Phase 3
**What goes wrong:** Planning stalls because the implementation tries to land durable Postgres persistence, artifact storage, and full progress introspection all at once.
**Why it happens:** Deep Agents threads and checkpoints naturally lead into Phase 3 concerns.
**How to avoid:** For Phase 2, use `InMemorySaver` plus a minimal run record, but keep the interfaces shaped for a later swap to `PostgresSaver`.
**Warning signs:** The plan starts introducing database migrations or production durability work for a phase that only needs same-thread clarification resume.

## Code Examples

Verified patterns from official sources:

### Create A Deep Agent With Checkpointed Thread State
```python
# Source: https://docs.langchain.com/oss/python/deepagents/customization
from deepagents import create_deep_agent
from langgraph.checkpoint.memory import InMemorySaver

agent = create_deep_agent(
    model="openai:gpt-5",
    tools=[web_search_tool, open_url_tool],
    checkpointer=InMemorySaver(),
)

result = agent.invoke(
    {"messages": [{"role": "user", "content": "Research battery supply chains"}]},
    config={"configurable": {"thread_id": "run-123"}},
)
```

### Resume The Same Thread After A Clarification Answer
```python
# Source: https://docs.langchain.com/oss/python/langgraph/persistence
agent.invoke(
    {"messages": [{"role": "user", "content": "Focus on North America only."}]},
    config={"configurable": {"thread_id": "run-123"}},
)
```

### Use Phase-2 App State Only For Clarification Gating
```python
def resume_after_clarification(run_state: DeepResearchRunState, answer: str) -> None:
    if run_state.pending_clarification is None:
        raise ValueError("Run is not awaiting clarification")

    run_state.pending_clarification = None
    run_state.status = "running"
    invoke_deep_research_turn(run_id=run_state.run_id, user_message=answer)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Custom long-running “deep research” job coordinators | Deep Agents supervisor with built-in planning, subagents, filesystem, and checkpoints | Deep Agents package line through 2025-2026 | Prefer `create_deep_agent(...)` over repo-local orchestration for deep research. |
| Replaying chat history manually for continuation | Resume via checkpointed `thread_id` | Current LangGraph persistence model | Resume logic should key off threads, not rebuilt prompt transcripts. |
| Treating deep research as a bigger synchronous agent profile | Dedicated deep-research run lifecycle with thread state | Current repo roadmap plus Deep Agents docs | Keep `deep_research` on its own runtime/service path. |

**Deprecated/outdated:**
- Placeholder queued flow in [backend/agent/deep_research_runtime.py](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/agent/deep_research_runtime.py): fine as Phase 1 scaffolding, but not acceptable for Phase 2 implementation.
- Local Python 3.9 as package-truth source: outdated for Deep Agents planning because `deepagents` requires Python 3.11+.

## Open Questions

1. **Should the resume API be a new endpoint or an optional field on the existing start request?**
   - What we know: the current request model has only `prompt`, `mode`, and `retrieval_policy`.
   - What's unclear: whether you want explicit transport separation for “new run” vs “answer clarification”.
   - Recommendation: use a dedicated resume endpoint and dedicated Pydantic request model.

2. **How should clarification detection be implemented in Phase 2?**
   - What we know: the one-question guarantee needs stronger control than prompt text alone.
   - What's unclear: whether to use an outer preflight classifier or allow the Deep Agent to ask the first clarification and then gate it app-side.
   - Recommendation: keep the Deep Agent as the runtime, but enforce unresolved-question count app-side. If determinism is still weak in testing, add a small structured preflight classifier as a follow-up refinement.

3. **Do you want streamed clarification events now or only a synchronous prompt/response handshake?**
   - What we know: the frontend already has background run/event infrastructure and `deep_research` is treated as a background surface.
   - What's unclear: whether the clarification request should appear as a terminal run-state event or a separate API response path.
   - Recommendation: represent clarification as a run-state transition plus a payloaded event so the existing run-history path can observe it.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | `pytest 7.1.2` for backend, `vitest 4.1.0` for frontend |
| Config file | `backend/tests/conftest.py`; no dedicated `pytest.ini` found |
| Quick run command | `python3 -m pytest backend/tests/agent/test_deep_research_runtime.py backend/tests/api/test_agent_run_service.py backend/tests/api/test_agent_run_route.py -q` |
| Full suite command | `python3 -m pytest backend/tests -q && npm run test` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DEEP-01 | `deep_research` start path uses Deep Agents service instead of placeholder queue runtime | backend unit/integration | `python3 -m pytest backend/tests/api/test_agent_run_service.py backend/tests/agent/test_deep_research_runtime.py -q` | ✅ |
| DEEP-02 | only one clarification can be outstanding | backend unit | `python3 -m pytest backend/tests/agent/test_deep_research_runtime.py -k clarification -q` | ❌ Wave 0 |
| DEEP-03 | answering clarification resumes same thread/run | backend integration | `python3 -m pytest backend/tests/api/test_agent_run_route.py -k resume -q` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `python3 -m pytest backend/tests/agent/test_deep_research_runtime.py backend/tests/api/test_agent_run_service.py backend/tests/api/test_agent_run_route.py -q`
- **Per wave merge:** `python3 -m pytest backend/tests -q`
- **Phase gate:** `python3 -m pytest backend/tests -q && npm run test`

### Wave 0 Gaps
- [ ] `backend/tests/agent/test_deep_agents_service.py` — covers DEEP-01 and DEEP-02 against the new service layer
- [ ] `backend/tests/api/test_deep_research_resume_route.py` — covers DEEP-03 resume transport
- [ ] clarification event assertions in `backend/tests/api/test_agent_run_route.py` or a new stream-focused test file
- [ ] backend container or Python 3.12 test path for dependency validation once `deepagents` is added

## Sources

### Primary (HIGH confidence)
- Official Deep Agents customization docs: https://docs.langchain.com/oss/python/deepagents/customization
- Official Deep Agents backends docs: https://docs.langchain.com/oss/python/deepagents/backends
- Official Deep Agents streaming docs: https://docs.langchain.com/oss/python/deepagents/streaming
- Official LangGraph persistence docs: https://docs.langchain.com/oss/python/langgraph/persistence
- Official LangGraph memory docs: https://docs.langchain.com/oss/python/langgraph/add-memory
- Official LangChain built-in middleware docs: https://docs.langchain.com/oss/python/langchain/middleware/built-in
- PyPI `deepagents`: https://pypi.org/project/deepagents/
- PyPI `langchain`: https://pypi.org/project/langchain/
- PyPI `langchain-openai`: https://pypi.org/project/langchain-openai/
- PyPI `langgraph`: https://pypi.org/project/langgraph/
- PyPI `langgraph-checkpoint-postgres`: https://pypi.org/project/langgraph-checkpoint-postgres/
- Current repo runtime files: [backend/api/services/agent_run.py](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/api/services/agent_run.py), [backend/agent/deep_research_runtime.py](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/agent/deep_research_runtime.py), [backend/agent/deep_research_store.py](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/agent/deep_research_store.py), [backend/agent/schemas/deep_research.py](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/agent/schemas/deep_research.py)

### Secondary (MEDIUM confidence)
- None needed

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - package versions and Python requirements were verified against official PyPI pages and official docs.
- Architecture: HIGH - recommendations align with official Deep Agents/LangGraph thread and checkpoint patterns plus verified current repo seams.
- Pitfalls: HIGH - directly supported by official docs and current repo mismatch analysis.

**Research date:** 2026-03-24
**Valid until:** 2026-03-31
