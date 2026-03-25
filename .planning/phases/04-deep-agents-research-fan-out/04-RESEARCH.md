# Phase 4: Deep Agents Research Fan-Out - Research

**Researched:** 2026-03-24
**Domain:** Deep Agents subagent delegation over an existing retrieval stack
**Confidence:** MEDIUM

## User Constraints

No phase-specific `CONTEXT.md` exists for Phase 4, so there are no additional locked decisions beyond the roadmap, requirements, `PROJECT.md`, and repo `AGENTS.md`.

Repo constraints that materially affect planning:
- Keep deep-research orchestration isolated to the deep-research backend path.
- Reuse the existing retrieval stack instead of building a new search/crawl system.
- Keep progress inspectable through persisted artifacts and logging rather than requiring new frontend work.
- Keep backend orchestration split into focused modules; do not grow `backend/agent/runtime.py` into a monolith.
- Prefer explicit Pydantic models in feature-local `schemas/` folders for stable backend contracts.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RSCH-01 | User can have the orchestrator spawn parallel research subagents for subquestions generated from the plan. | Use Deep Agents `subagents` plus the built-in `task` tool, with the supervisor owning plan fan-out and subagent artifact collection. |
| RSCH-02 | User can have each research subagent use the same retrieval capabilities the project already exposes for web search and URL opening. | Reuse shared retrieval-tool factories built from the existing `web_search` and current crawl/open tool behavior, and inject those tools explicitly into each custom subagent. |
</phase_requirements>

## Summary

Phase 4 should be planned as a Deep Agents-native delegation layer, not as a custom fan-out executor. The official Deep Agents model is: a supervisor created with `create_deep_agent(...)` delegates independent work through the built-in `task` tool to configured subagents. Official LangChain subagent guidance also states the main agent can invoke multiple subagents in a single turn, which is the right fit for plan-derived subquestions.

The existing repo already has the right substrate for evidence collection: typed `web_search` and crawl/open tool contracts, retrieval-policy enforcement, typed source schemas, and normalization helpers in [runtime_sources.py](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/agent/runtime_sources.py). The critical design point is that Deep Agents custom subagents do not inherit the parent agent’s tools or system prompt, so this phase must explicitly inject the shared retrieval behavior into every research subagent rather than assuming inheritance.

The largest planning risk is compatibility, not orchestration logic. Current official `deepagents` releases require Python `>=3.11` and `langchain >=1.2.x`, while this repo is pinned to Python 3.9 locally, `langchain==0.3.27`, `langgraph==0.6.11`, and does not have `deepagents` installed. If earlier phases do not absorb that migration, Phase 4 needs a Wave 0 compatibility/install task before any fan-out work.

**Primary recommendation:** Plan Phase 4 around one supervisor Deep Agent, one reusable research subagent spec, explicit retrieval-tool injection, per-subquestion artifact writes, and a prerequisite Deep Agents stack compatibility gate.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `deepagents` | `0.4.12` (PyPI uploaded 2026-03-20) | Supervisor + `task`-based subagent delegation, filesystem tools, Deep Agents harness | Official Deep Agents package for planning, subagents, and backend routing |
| `langchain` | `1.2.13` (PyPI uploaded 2026-03-19) | Agent/model/tool integration layer required by current Deep Agents | Current Deep Agents releases require `langchain >=1.2.11` |
| `langchain-openai` | `1.1.12` (PyPI uploaded 2026-03-23) | OpenAI chat model integration for supervisor/subagents | Keeps the project on the current LangChain provider package line |
| `langgraph` | `1.1.3` (PyPI uploaded 2026-03-18) | Durable execution runtime beneath Deep Agents | Current official stack line for Deep Agents-era LangGraph |
| `langgraph-checkpoint-postgres` | `3.0.5` (PyPI uploaded 2026-03-18) | Resume/checkpoint persistence for background deep-research threads | Current Postgres checkpointer line paired with the current LangGraph stack |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `deepagents.backends.StateBackend` | bundled with `deepagents 0.4.12` | Per-thread artifact workspace | Default backend for `/workspace/*` scratch files |
| `deepagents.backends.StoreBackend` | bundled with `deepagents 0.4.12` | Cross-thread durable file storage via LangGraph store | Persist research artifacts or reusable memory across runs |
| `deepagents.backends.CompositeBackend` | bundled with `deepagents 0.4.12` | Path-based backend routing | Keep plan scratch files ephemeral while persisting selected research artifacts |
| Existing repo retrieval tools | local code | `web_search` plus current crawl/open behavior and source normalization | Reuse instead of building new Deep Agents-specific retrieval tools |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Official `deepagents` + `task` tool | Custom `asyncio` or background-job fan-out in `backend/agent/*` | Avoids dependency migration, but abandons the roadmap’s `create_deep_agent(...)` direction and re-implements subagent orchestration |
| Explicit retrieval tool injection per subagent | Let subagents fall back to generic/default tools | Incorrect for custom subagents because Deep Agents docs state custom subagents do not inherit parent tools |
| Artifact-backed progress | Only in-memory job state | Fails the inspectable-progress requirement and makes resume/debugging weaker |

**Installation:**
```bash
pip install \
  "deepagents==0.4.12" \
  "langchain==1.2.13" \
  "langchain-openai==1.1.12" \
  "langgraph==1.1.3" \
  "langgraph-checkpoint-postgres==3.0.5"
```

**Version verification:** Verified against current PyPI metadata on 2026-03-24.

**Compatibility note:** Current repo state is not ready for this stack:
- Local Python is `3.9.13`, but current `deepagents` requires `>=3.11`.
- [backend/requirements.txt](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/requirements.txt) pins `langchain==0.3.27`, `langchain-openai==0.3.35`, and `langgraph==0.6.11`.
- `deepagents` is not installed in the current environment.

## Architecture Patterns

### Recommended Project Structure
```text
backend/agent/
├── deep_research_supervisor.py        # Build/configure the Deep Agents supervisor
├── deep_research_subagents.py         # Custom research-subagent specs and result schema
├── deep_research_retrieval_tools.py   # Shared web_search/open_url tool factories
├── deep_research_artifacts.py         # Persist plan/subanswer/evidence artifacts
├── deep_research_progress.py          # Progress event and status recording
├── deep_research_runtime.py           # Thin lifecycle entrypoint only
└── schemas/
    ├── deep_research.py               # Job/stage models
    └── deep_research_subagent.py      # Subanswer/evidence payload models
```

### Pattern 1: Supervisor Owns Plan-Derived Fan-Out
**What:** Build one Deep Agents supervisor that reads the persisted plan, delegates each subquestion with the built-in `task` tool, and collects concise subagent results.
**When to use:** Always for Phase 4. Do not make the API route or background job runner spawn ad hoc worker functions directly.
**Example:**
```python
from deepagents import create_deep_agent

agent = create_deep_agent(
    model="openai:gpt-5",
    system_prompt=(
        "You are the deep-research supervisor. "
        "Delegate each independent subquestion to a research subagent."
    ),
    subagents=[research_subagent],
)
```
Source: https://docs.langchain.com/oss/python/deepagents/overview

### Pattern 2: Explicit Retrieval Tool Injection Per Subagent
**What:** Build a shared retrieval-tool factory from the repo’s existing retrieval policy and pass those tools directly to every custom subagent.
**When to use:** Always. Deep Agents docs explicitly say custom subagents do not inherit parent tools or system prompts.
**Example:**
```python
research_subagent = {
    "name": "research-agent",
    "description": "Used to research one subquestion in depth.",
    "system_prompt": "Return a concise subanswer with reusable evidence.",
    "tools": [web_search_tool, open_url_tool],
}
```
Source: https://docs.langchain.com/oss/python/deepagents/subagents

### Pattern 3: Artifact-First Evidence Handoff
**What:** Have each subagent return a concise result message and also write detailed notes/evidence to routed backend files such as `/workspace/research/<slug>.md` or `/memories/research/<run>/<slug>.json`.
**When to use:** For all non-trivial subquestions where the tool output is larger than what the supervisor should keep in-context.
**Example:**
```python
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend

backend = lambda rt: CompositeBackend(
    default=StateBackend(rt),
    routes={"/memories/": StoreBackend(rt)},
)
```
Source: https://docs.langchain.com/oss/python/deepagents/backends

### Pattern 4: Typed Subagent Result Envelope
**What:** Define one Pydantic schema for a subagent result containing `subquestion`, `answer`, `sources`, `citations`, and `artifact_path`, then validate every returned subagent payload before synthesis.
**When to use:** In Phase 4 for best-effort structure; Phase 5 can harden enforcement with middleware.
**Example:**
```python
class DeepResearchSubagentResult(BaseModel):
    subquestion: str
    answer: str
    sources: list[AgentSourceReference] = Field(default_factory=list)
    citations: list[AgentAnswerCitation] = Field(default_factory=list)
    artifact_path: str | None = None
```
Source: local repo schema pattern in [__init__.py](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/agent/schemas/__init__.py)

### Anti-Patterns to Avoid
- **Custom fan-out loop hidden behind generic runners:** The roadmap explicitly targets Deep Agents delegation, and the repo guidance prefers direct runtime paths over opaque runner indirection.
- **Putting subagent logic into `backend/agent/runtime.py`:** The repo explicitly says not to let orchestration grow monolithic.
- **Letting subagents emit raw tool payloads as their final answer:** Official docs call out context bloat; return a concise summary and persist the large evidence elsewhere.
- **Creating a second retrieval stack for Deep Agents:** Reuse [web_search.py](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/app/tools/web_search.py), [web_crawl.py](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/app/tools/web_crawl.py), and [runtime_sources.py](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/agent/runtime_sources.py).
- **Assuming `open_url` already exists:** Current runtime constants still use `web_crawl`; Phase 4 planning must either depend on Phase 1 completion or add a compatibility alias.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Deep research subagent orchestration | Custom worker queue plus homemade delegation prompts | Deep Agents `subagents` plus built-in `task` tool | Official harness already handles subagent spawning and metadata |
| Research artifact routing | Ad hoc local file writes sprinkled through runtime code | `StateBackend` / `StoreBackend` / `CompositeBackend` | Official backend routing is built for this exact filesystem abstraction |
| Evidence normalization per worker | Repeated dict parsing in each fan-out branch | Existing `AgentSourceReference`, `AgentAnswerCitation`, and `runtime_sources` helpers | Keeps source IDs, alias handling, and citation hydration consistent |
| Progress inspection | New bespoke frontend transport for this phase | Persisted artifacts plus existing run-event/logging surfaces | Roadmap says no new frontend is required for current milestone |

**Key insight:** The repo already has mature typed retrieval and evidence-normalization layers. The part you should not custom-build is the subagent harness around them.

## Common Pitfalls

### Pitfall 1: Custom Subagents Do Not Inherit Tools
**What goes wrong:** The supervisor has the right retrieval tools, but delegated subagents do not, so they cannot search or open pages.
**Why it happens:** Deep Agents docs explicitly say custom subagents do not inherit the main agent’s tools or system prompt.
**How to avoid:** Build one shared retrieval-tool factory and inject those tools into each custom subagent spec.
**Warning signs:** Delegated tasks complete with generic text but no search/crawl tool calls or evidence.

### Pitfall 2: Current Repo Stack Is Incompatible With Current Deep Agents
**What goes wrong:** Planning assumes this phase is only orchestration work, but implementation stalls on imports, version conflicts, or Python constraints.
**Why it happens:** Current official `deepagents` requires Python `>=3.11` and `langchain >=1.2.x`, while the repo is on Python 3.9 locally and LangChain 0.3 packages.
**How to avoid:** Add a Wave 0 compatibility task or confirm earlier phases already upgraded the stack.
**Warning signs:** `ModuleNotFoundError: deepagents`, resolver conflicts, or Docker/local version drift.

### Pitfall 3: Context Bloat From Raw Research Dumps
**What goes wrong:** The supervisor’s context fills with raw search snippets and long crawl output from every subagent.
**Why it happens:** Subagents return intermediate tool output instead of a concise subanswer plus artifact pointer.
**How to avoid:** Require concise subagent output and move detailed evidence into backend-routed files.
**Warning signs:** Long final messages, repeated raw payloads, or missing room for synthesis.

### Pitfall 4: Tool Contract Drift Between Roadmap and Runtime
**What goes wrong:** Planner targets `open_url`, but implementation reuses `web_crawl` directly and creates contract drift.
**Why it happens:** Phase 1 is not reflected in the current backend yet; current canonical tool names remain `("web_search", "web_crawl")`.
**How to avoid:** Either land the Phase 1 rename first or introduce a single compatibility alias and use that everywhere in Deep Agents wiring.
**Warning signs:** Tests and prompts refer to both `open_url` and `web_crawl`.

### Pitfall 5: Parallelism Without Observable Progress
**What goes wrong:** Subagents run, but users and operators cannot tell which subquestion is pending, complete, or failed.
**Why it happens:** Fan-out is implemented as opaque background calls without artifact/status writes.
**How to avoid:** Persist one artifact/status record per subquestion and emit run events keyed by subquestion/subagent name.
**Warning signs:** Background jobs appear stalled even when work is progressing.

## Code Examples

Verified patterns from official sources:

### Define A Deep Agent Supervisor
```python
from deepagents import create_deep_agent

agent = create_deep_agent(
    tools=[get_weather],
    system_prompt="You are a helpful assistant",
)
```
Source: https://docs.langchain.com/oss/python/deepagents/overview

### Define A Custom Subagent
```python
research_subagent = {
    "name": "research-agent",
    "description": "Used to research more in depth questions",
    "system_prompt": "You are a great researcher",
    "tools": [internet_search],
}
```
Source: https://docs.langchain.com/oss/python/deepagents/subagents

### Route Artifacts With A Composite Backend
```python
from deepagents.backends import CompositeBackend, StateBackend, StoreBackend

backend = lambda rt: CompositeBackend(
    default=StateBackend(rt),
    routes={"/memories/": StoreBackend(rt)},
)
```
Source: https://docs.langchain.com/oss/python/deepagents/backends

### Use Subagent Metadata Inside Shared Tools
```python
@tool
def flexible_search(query: str, config) -> str:
    agent_name = config.get("metadata", {}).get("lc_agent_name", "unknown")
    return perform_search(query, max_results=5 if agent_name == "research-agent" else 2)
```
Source: https://docs.langchain.com/oss/python/deepagents/subagents

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Custom or shallow single-agent loop | Deep Agents harness with planning, task delegation, backends, and memory | Deep Agents package line released 2025-2026; current stable `0.4.12` on 2026-03-20 | Prefer official Deep Agents primitives over homemade subagent orchestration |
| In-memory or local-thread filesystem only | `StateBackend` by default, with `StoreBackend` / `CompositeBackend` for durable routing | Current Deep Agents backend docs | Makes inspectable artifact persistence part of the standard design |
| Ad hoc subagent/tool metadata | `lc_agent_name` metadata and subagent streaming/status interfaces | Current Deep Agents and LangChain subagent docs | Makes per-subagent progress and tool attribution first-class |

**Deprecated/outdated:**
- In-repo placeholder deep-research execution in [deep_research_execution.py](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/agent/deep_research_execution.py): currently only increments `wave_count`; it is not a Deep Agents fan-out implementation.
- In-memory job storage in [deep_research_store.py](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/agent/deep_research_store.py): insufficient for the roadmap’s persistence and inspectability goals.

## Open Questions

1. **Will Phase 2/3 upgrade the backend to a Deep Agents-compatible stack before Phase 4 starts?**
   - What we know: Current repo/runtime is not compatible with current `deepagents`.
   - What's unclear: Whether that migration is intended as prior-phase work or must be absorbed here.
   - Recommendation: Treat dependency/runtime compatibility as a gate before planning implementation tasks.

2. **Should Phase 4 code against `open_url` or the current `web_crawl` implementation?**
   - What we know: Roadmap text says `open_url`, but local runtime still exposes `web_crawl`.
   - What's unclear: Whether the Phase 1 rename will be complete before this phase executes.
   - Recommendation: Add one explicit prerequisite task or alias decision in the plan.

3. **How much structure should Phase 4 enforce on subagent outputs before Phase 5 middleware exists?**
   - What we know: Success criteria expect subanswers, sources, and citations; Phase 5 is where middleware enforcement is planned.
   - What's unclear: Whether Phase 4 should fail on malformed outputs or normalize best-effort and continue.
   - Recommendation: Use typed Pydantic validation now, but reserve hard enforcement/retry policy for Phase 5.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | `pytest 7.1.2` |
| Config file | none — pytest autodiscovery |
| Quick run command | `pytest backend/tests/agent/test_deep_research_runtime.py -q` |
| Full suite command | `pytest backend/tests -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RSCH-01 | Supervisor delegates plan-derived subquestions to parallel Deep Agents subagents and records per-subquestion completion | unit/integration | `pytest backend/tests/agent/test_deep_research_subagents.py -q` | ❌ Wave 0 |
| RSCH-02 | Research subagents reuse the existing retrieval behavior and return normalized evidence-bearing results | unit/integration | `pytest backend/tests/agent/test_deep_research_subagents.py -q` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest backend/tests/agent/test_deep_research_subagents.py -q`
- **Per wave merge:** `pytest backend/tests/agent/test_deep_research_runtime.py -q`
- **Phase gate:** `pytest backend/tests -q`

### Wave 0 Gaps
- [ ] `backend/tests/agent/test_deep_research_subagents.py` — fan-out, retrieval reuse, and artifact/progress coverage for RSCH-01 and RSCH-02
- [ ] `backend/tests/agent/test_deep_research_runtime.py` — extend current placeholder coverage to assert fan-out stage transitions and artifact persistence
- [ ] Dependency smoke check — add a focused import/config test that fails clearly when `deepagents` or compatible package versions are missing

## Sources

### Primary (HIGH confidence)
- https://docs.langchain.com/oss/python/deepagents/overview - verified `create_deep_agent(...)`, task delegation, backends, and Deep Agents core capabilities
- https://docs.langchain.com/oss/python/deepagents/subagents - verified custom subagent configuration, non-inheritance of tools/system prompt, `lc_agent_name` metadata, and structured output notes
- https://docs.langchain.com/oss/python/deepagents/backends - verified `StateBackend`, `StoreBackend`, `CompositeBackend`, default backend behavior, and backend routing guidance
- https://docs.langchain.com/oss/python/deepagents/frontend/subagent-streaming - verified subagent status/result metadata and streaming model
- https://docs.langchain.com/oss/python/langchain/multi-agent/subagents - verified main-agent subagent pattern and explicit parallel execution in a single turn
- https://pypi.org/project/deepagents/ - verified current stable version `0.4.12`, release date, Python requirement, and package metadata
- https://pypi.org/pypi/deepagents/json - verified current dependency requirements for `deepagents`
- https://pypi.org/pypi/langchain/json - verified latest `langchain` version and upload date
- https://pypi.org/pypi/langchain-openai/json - verified latest `langchain-openai` version and upload date
- https://pypi.org/pypi/langgraph/json - verified latest `langgraph` version and upload date
- https://pypi.org/project/langgraph-checkpoint-postgres/ - verified current Postgres checkpointer release line
- https://pypi.org/pypi/langgraph-checkpoint-postgres/json - verified latest checkpointer version and dependencies

### Secondary (MEDIUM confidence)
- Local repo inspection of [deep_research_runtime.py](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/agent/deep_research_runtime.py), [deep_research_execution.py](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/agent/deep_research_execution.py), [web_search.py](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/app/tools/web_search.py), [web_crawl.py](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/app/tools/web_crawl.py), and [runtime_sources.py](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/agent/runtime_sources.py) - verified current integration points and evidence-normalization utilities
- Local repo inspection of [backend/Dockerfile](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/Dockerfile) and [docker-compose.yml](/Users/nickbohm/Desktop/Tinkering/web-agent/docker-compose.yml) - verified container Python version and backend runtime shape

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: MEDIUM - official docs and PyPI are clear, but the current repo is materially behind the compatible version line
- Architecture: HIGH - delegation, backend routing, and subagent configuration are explicitly documented and map cleanly onto the repo
- Pitfalls: HIGH - supported by both official docs and concrete repo inspection

**Research date:** 2026-03-24
**Valid until:** 2026-03-31
