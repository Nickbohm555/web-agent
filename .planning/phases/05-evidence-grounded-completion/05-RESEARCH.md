# Phase 5: Evidence-Grounded Completion - Research

**Researched:** 2026-03-24
**Domain:** Deep Agents evidence enforcement, middleware-driven normalization, and completion gating
**Confidence:** MEDIUM

<user_constraints>
## User Constraints (from CONTEXT.md)

No `*-CONTEXT.md` exists for this phase directory.

### Locked Decisions
- Phase description: Use middleware as an enforcement and normalization layer so synthesis only completes once evidence from each subagent result is extracted and sufficient.
- Keep the current top-level `deep_research` API response shape stable while evidence is carried inside AI message content.
- Requirements in scope: `RSCH-03`, `RSCH-04`, `DEEP-04`, `TOOL-03`.

### Claude's Discretion
- Choose the exact middleware hooks, subagent output contract, state fields, and sufficiency checks.
- Recommend the smallest doc-aligned stack needed to enforce evidence-grounded completion.

### Deferred Ideas (OUT OF SCOPE)
- Dedicated frontend deep-research inspection UI.
- Broad API envelope redesign for `deep_research`.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RSCH-03 | Each research subagent returns an AI message with normalized search-result sources and crawl-result citations. | Use typed subagent output schema plus middleware validation and normalization before the supervisor consumes results. |
| RSCH-04 | The orchestrator loops on research results until enough evidence exists. | Track evidence coverage in agent state and gate synthesis on a sufficiency function instead of one-pass completion. |
| DEEP-04 | Final deep-research answer is emitted only after planned subquestions are answered well enough. | Add a completion gate that requires per-subquestion evidence coverage before the synthesize/end path is allowed. |
| TOOL-03 | Keep current top-level API response shape while evidence lives inside AI message content via middleware. | Normalize evidence into `AgentStructuredAnswer` / `AgentSourceReference` internally, but keep `AgentRunSuccessResponse` unchanged. |
</phase_requirements>

## Summary

The current codebase does not yet implement Phase 5 behavior. `backend/agent/deep_research_runtime.py` always synthesizes after a single verifier pass, `backend/agent/deep_research_execution.py` only increments `wave_count`, and `backend/agent/deep_research_verification.py` marks the job complete with placeholder text. The existing evidence path is centered around `backend/agent/runtime_sources.py`, which already knows how to hydrate `AgentStructuredAnswer`, `AgentAnswerCitation`, and `AgentSourceReference`, but it still relies on fallback parsing of repr-like tool outputs. That is the wrong seam for Deep Agents completion gating.

The standard implementation pattern for this phase is: make each research subagent return a typed evidence bundle, use middleware to validate and normalize that bundle into agent state immediately after the subagent responds, and let the supervisor synthesize only when a deterministic sufficiency function says every planned research thread is covered. This matches LangChain middleware hooks (`before_model`, `after_model`, `wrap_model_call`) and Deep Agents’ documented support for subagents, custom middleware, and structured output.

The highest-risk project issue is environmental, not algorithmic: the current local Python runtime is `3.9.13`, while `deepagents` `0.4.12` requires Python `>=3.11`. If Phases 2-4 have not already moved the backend runtime to 3.11+, Phase 5 planning must include that as a prerequisite or the middleware/subagent architecture in the roadmap cannot run.

**Primary recommendation:** Implement Phase 5 with a compiled research subagent that emits a Pydantic evidence contract, a class-based middleware layer that validates and stores normalized evidence in state after each subagent/model result, and a supervisor-side sufficiency gate that blocks synthesis until every planned subquestion has usable evidence.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `deepagents` | `0.4.12` (released 2026-03-20) | Deep Agents supervisor + subagent orchestration | Official package for Deep Agents; docs explicitly support middleware, subagents, backends, and structured output. |
| `langchain` | `1.2.13` (released 2026-03-19) | Middleware hooks and agent runtime primitives | Official middleware docs and current Deep Agents docs are written against the modern LangChain agent runtime. |
| `langgraph` | `0.6.11` (installed current repo; latest detected locally) | State graph execution and reducer-based state updates | Middleware state updates and Deep Agents execution sit on LangGraph semantics. |
| `pydantic` | `2.x` (repo already uses it) | Evidence contract validation | The repo already relies on strict Pydantic validation for runtime/API evidence objects. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `langchain-openai` | `0.3.35` (installed current repo) | Chat model integration for OpenAI-backed agent/subagent execution | Use when the repo keeps OpenAI-backed research workers. |
| `langgraph-checkpoint-postgres` | `2.0.25` (latest detected locally) | Durable resume for interrupted deep-research threads | Needed when Phase 5 must preserve progress through retries or human pauses. |
| `pytest` | existing repo runner | Backend middleware, normalization, and gating tests | Use for all Phase 5 backend behavior and regression coverage. |
| `vitest` | `4.1.0` from `package.json` | Frontend/API contract validation | Use only for envelope-parity tests if the streamed/completed payload contract changes indirectly. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Typed subagent evidence schema | Free-form markdown or ad hoc JSON in message text | Easier to start, but it recreates the current fragile parsing problem. |
| Middleware state updates | Post-hoc regex extraction from saved messages | Lower upfront work, but too brittle for completion gating. |
| Supervisor completion gate | Let the model decide when it is “done” | Faster to prototype, but it does not satisfy `DEEP-04` reliably. |

**Installation:**
```bash
python3.11 -m pip install -U deepagents langchain langgraph langgraph-checkpoint-postgres
python3.11 -m pip install -r backend/requirements.txt
```

**Version verification:** Before implementation, re-check live versions because this stack is moving quickly.
```bash
python3.11 -m pip index versions deepagents
python3.11 -m pip index versions langchain
python3.11 -m pip index versions langgraph
python3.11 -m pip index versions langgraph-checkpoint-postgres
```

## Architecture Patterns

### Recommended Project Structure
```text
backend/agent/
├── middleware/
│   ├── evidence_completion.py      # class-based middleware hooks
│   ├── evidence_state.py           # custom AgentState / reducers
│   └── evidence_normalization.py   # subagent payload -> repo schemas
├── schemas/
│   ├── deep_research.py
│   └── evidence_completion.py      # subagent output + sufficiency models
├── deep_research_execution.py      # research loop orchestration only
├── deep_research_verification.py   # sufficiency checks only
└── deep_research_runtime.py        # wiring only
```

### Pattern 1: Typed Subagent Evidence Contract
**What:** Each research subagent returns a structured bundle with `subquestion`, `answer_text`, `sources`, `citations`, and a machine-checkable `sufficiency` flag/reason.
**When to use:** For every delegated research thread whose result must influence completion.
**Example:**
```python
# Source pattern: https://docs.langchain.com/oss/python/deepagents/subagents
# and https://docs.langchain.com/oss/python/deepagents/customization
from pydantic import BaseModel, Field


class ResearchEvidenceResult(BaseModel):
    subquestion: str = Field(min_length=1)
    answer_text: str = Field(min_length=1)
    sources: list[dict] = Field(default_factory=list)
    citations: list[dict] = Field(default_factory=list)
    is_sufficient: bool = False
    insufficiency_reason: str = ""
```

### Pattern 2: Middleware Normalizes Immediately After Model/Subagent Output
**What:** Use class-based middleware so `after_model` validates the latest AI message or structured response, converts it into repo-native evidence models, and writes normalized coverage into state.
**When to use:** Whenever a subagent returns evidence that the supervisor will rely on later.
**Example:**
```python
# Source pattern: https://docs.langchain.com/oss/python/langchain/middleware/custom
from langchain.agents.middleware import AgentMiddleware


class EvidenceCompletionMiddleware(AgentMiddleware):
    state_schema = DeepResearchEvidenceState

    def after_model(self, state, runtime):
        normalized = normalize_latest_research_result(state)
        if normalized is None:
            return None
        return {
            "evidence_by_subquestion": {
                **state.get("evidence_by_subquestion", {}),
                normalized.subquestion: normalized,
            }
        }
```

### Pattern 3: Supervisor Completion Gate Uses Deterministic Sufficiency
**What:** The agent runtime decides “done” from state, not from the model’s preference. Every planned subquestion must have a normalized result and minimum evidence coverage before synthesis.
**When to use:** Before any `SYNTHESIZING` or `COMPLETED` transition.
**Example:**
```python
def is_research_complete(plan_subquestions: list[str], evidence_by_subquestion: dict[str, ResearchEvidenceResult]) -> bool:
    for subquestion in plan_subquestions:
        result = evidence_by_subquestion.get(subquestion)
        if result is None:
            return False
        if not result.is_sufficient:
            return False
        if not result.sources and not result.citations:
            return False
    return True
```

### Pattern 4: Keep the Existing API Envelope as an Adapter
**What:** Preserve `AgentRunSuccessResponse` and convert the final synthesized state back into `AgentStructuredAnswer` plus `sources`.
**When to use:** At the boundary in `backend/api/services/agent_run.py` and the deep-research completion serializer.
**Example:**
```python
def build_completed_run(job: DeepResearchJob) -> AgentRunSuccessResponse:
    structured_answer = build_structured_answer_from_state(job)
    source_list = build_source_list_from_state(job)
    return AgentRunSuccessResponse.from_run_result(
        AgentRunResult(
            run_id=job.job_id,
            status="completed",
            final_answer=structured_answer,
            sources=source_list,
            tool_call_count=0,
            elapsed_ms=0,
        )
    )
```

### Anti-Patterns to Avoid
- **Regex-first evidence recovery:** Do not make Phase 5 depend on `repr` parsing in `runtime_sources.py` for the new Deep Agents path.
- **Single monolithic runtime file:** Keep middleware, normalization, sufficiency logic, and runtime wiring in separate modules per repo instructions.
- **Model-decides-finished behavior:** Completion must be state-driven, not just whatever the final model message says.
- **Schema drift between internal evidence and API contracts:** Reuse `AgentStructuredAnswer`, `AgentAnswerCitation`, and `AgentSourceReference` as the normalization target.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Subagent orchestration | Custom fan-out/fan-in scheduler around raw chat calls | Deep Agents subagents / compiled subagents | Deep Agents already provides subagent isolation, task delegation, and middleware insertion points. |
| Evidence validation | Manual dict checks spread across runtime files | Pydantic evidence models in feature-local `schemas/` | Centralized validation keeps normalization deterministic. |
| Completion gating | Ad hoc string heuristics like “answer looks complete” | Deterministic sufficiency function over normalized state | Requirement coverage depends on per-subquestion evidence, not prose quality. |
| Message-history interception | Custom wrapper layer around every tool/model call | LangChain middleware hooks | Official hooks already support `before_model`, `after_model`, and `wrap_model_call`. |

**Key insight:** Phase 5 is mostly a state-contract problem, not a prompting problem. Prompt reminders help, but only typed validation plus deterministic gating actually satisfy the requirements.

## Common Pitfalls

### Pitfall 1: Trying to Finish From Free-Form Subagent Summaries
**What goes wrong:** A subagent returns a nice paragraph, but sources/citations are missing or malformed.
**Why it happens:** The parent agent only receives concise subagent output by design, so unstructured summaries silently drop the evidence needed for completion gating.
**How to avoid:** Give each custom research subagent an explicit output contract and validate it in middleware immediately.
**Warning signs:** Final synthesis has text but `sources == []`, or citations reference source IDs that were never normalized.

### Pitfall 2: Depending on the Current Python 3.9 Runtime
**What goes wrong:** Deep Agents cannot be installed or run as documented.
**Why it happens:** `deepagents` `0.4.12` requires Python `>=3.11`, while the current local runtime is `3.9.13`.
**How to avoid:** Treat Python 3.11+ as a phase prerequisite unless earlier phases already upgraded the backend runtime.
**Warning signs:** `pip` cannot resolve `deepagents`, or CI/test envs disagree on supported versions.

### Pitfall 3: Treating “One Source Exists” as Sufficient Evidence
**What goes wrong:** The supervisor synthesizes too early from one partial thread.
**Why it happens:** The current placeholder runtime has no coverage model and no per-subquestion sufficiency state.
**How to avoid:** Require a normalized evidence record for every planned subquestion, with explicit insufficiency reasons when follow-up research is still needed.
**Warning signs:** `wave_count` increments, but there is no mapping from planned subquestions to verified evidence.

### Pitfall 4: Letting Middleware Mutate the API Contract
**What goes wrong:** Frontend/API tests break because deep-research completion payloads change shape.
**Why it happens:** Internal evidence schema additions leak through the route serializer.
**How to avoid:** Keep middleware-only fields in agent state and translate back to the existing `AgentRunSuccessResponse` boundary.
**Warning signs:** `backend/tests/api/test_agent_run_route.py` or `src/tests/frontend-api/*.test.ts` start failing on envelope shape, not on evidence semantics.

## Code Examples

Verified patterns from official sources:

### Class-Based Evidence Middleware
```python
# Source pattern: https://docs.langchain.com/oss/python/langchain/middleware/custom
from langchain.agents import create_agent

agent = create_agent(
    model=model,
    tools=tools,
    middleware=[EvidenceCompletionMiddleware()],
    state_schema=DeepResearchEvidenceState,
)
```

### Custom Research Subagent With Dedicated Tools And Middleware
```python
# Source pattern: https://docs.langchain.com/oss/python/deepagents/subagents
research_subagent = {
    "name": "evidence-researcher",
    "description": "Research one subquestion and return evidence-bearing results only.",
    "system_prompt": "Return a concise answer plus normalized evidence fields.",
    "tools": [web_search, open_url],
    "middleware": [EvidenceCompletionMiddleware()],
}
```

### Structured Output For Subagent Result Validation
```python
# Source pattern: https://docs.langchain.com/oss/python/deepagents/customization
compiled_subagent = create_agent(
    model=model,
    tools=[web_search, open_url],
    response_format=ResearchEvidenceResult,
)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Recover sources from tool-message repr parsing | Validate structured subagent outputs, then normalize into state | Current LangChain / Deep Agents docs | Much lower risk of silent evidence loss. |
| Let the model decide when research is complete | Gate completion on deterministic sufficiency over normalized state | Current middleware/state-driven agent patterns | Satisfies `DEEP-04` and `RSCH-04` more reliably. |
| Use one agent context for everything | Delegate heavy retrieval to subagents and return concise validated results | Current Deep Agents subagent guidance | Keeps supervisor context clean while preserving evidence. |

**Deprecated/outdated:**
- Repo-local placeholder completion in `backend/agent/deep_research_verification.py`: fine for scaffolding, but not acceptable once evidence-grounded completion is implemented.
- Repr-based extraction as the primary path for Deep Agents: keep only as legacy fallback for older runtimes, not as the standard Phase 5 path.

## Open Questions

1. **Which exact LangChain release line will Phases 2-4 land on?**
   - What we know: Current docs are for the modern middleware/runtime surface; the repo still pins `langchain==0.3.27`.
   - What's unclear: Whether earlier phases will upgrade to the 1.x docs line before Phase 5 work starts.
   - Recommendation: Treat this as a phase-entry check. If the runtime is still on 0.3.x, do the version-alignment work before designing middleware details.

2. **Will custom research workers be dictionary subagents or compiled subagents?**
   - What we know: Deep Agents supports both; compiled subagents are the cleaner fit when you need stronger output validation.
   - What's unclear: Whether Phase 4 will already have created custom compiled research subagents.
   - Recommendation: Prefer compiled subagents for evidence-bearing research workers; use dictionary subagents only if the existing Phase 4 design already depends on them.

3. **Where should insufficiency reasons be stored for follow-up waves?**
   - What we know: Middleware and LangGraph state updates can store extra fields cleanly.
   - What's unclear: Whether the project wants them persisted on `DeepResearchJob`, artifact files, or both.
   - Recommendation: Store them in runtime state first and persist the normalized summary onto `DeepResearchJob` for observability.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | `pytest` for backend, `vitest 4.1.0` for TypeScript contract checks |
| Config file | none for both; backend bootstraps via `backend/tests/conftest.py`, frontend via `package.json` |
| Quick run command | `pytest backend/tests/agent/test_deep_research_runtime.py -q` |
| Full suite command | `pytest backend/tests -q && npm test` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RSCH-03 | Subagent result is normalized into answer + sources + citations | unit | `pytest backend/tests/agent/test_evidence_completion.py -q` | ❌ Wave 0 |
| RSCH-04 | Research loop continues until sufficiency is met | unit/integration | `pytest backend/tests/agent/test_deep_research_runtime.py -q` | ✅ |
| DEEP-04 | Final synthesis/completion is blocked until all planned subquestions are covered | integration | `pytest backend/tests/agent/test_deep_research_runtime.py -q` | ✅ |
| TOOL-03 | Completed API payload keeps existing top-level envelope while carrying structured evidence | API contract | `pytest backend/tests/api/test_agent_run_route.py -q` | ✅ |

### Sampling Rate
- **Per task commit:** `pytest backend/tests/agent/test_deep_research_runtime.py -q`
- **Per wave merge:** `pytest backend/tests -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/agent/test_evidence_completion.py` — middleware validation, normalization, and insufficiency-state coverage for `RSCH-03` / `RSCH-04`
- [ ] `backend/tests/agent/test_deep_research_runtime.py` additions — assert that synthesis does not run when evidence is incomplete
- [ ] `backend/tests/api/test_agent_run_route.py` additions — assert unchanged envelope with evidence-rich final answer content
- [ ] Python runtime upgrade path to `3.11+` in local/CI/dev containers if not already completed in earlier phases

## Sources

### Primary (HIGH confidence)
- https://docs.langchain.com/oss/python/langchain/middleware/custom - verified middleware hooks, state updates, and class-based middleware patterns
- https://docs.langchain.com/oss/python/deepagents/customization - verified Deep Agents middleware, `response_format`, and customization points
- https://docs.langchain.com/oss/python/deepagents/subagents - verified subagent configuration, compiled subagents, and structured-output guidance
- https://docs.langchain.com/oss/python/deepagents/backends - verified backend/storage patterns that Phase 5 assumes from Phase 3
- https://pypi.org/project/deepagents/ - verified `deepagents` current stable version and Python requirement
- https://pypi.org/project/langchain/ - verified current published `langchain` version

### Secondary (MEDIUM confidence)
- Local repo code in `backend/agent/deep_research_runtime.py`, `backend/agent/deep_research_execution.py`, `backend/agent/deep_research_verification.py`, and `backend/agent/runtime_sources.py` - used to map official patterns onto the actual code seams
- Local package metadata via `python3 -m pip index versions langchain`, `langgraph`, and `langgraph-checkpoint-postgres` - used to confirm currently installable versions in this environment

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: MEDIUM - official docs and package pages are clear, but the repo is still on an older LangChain/Python runtime line
- Architecture: HIGH - official middleware and subagent docs map directly to the phase goal
- Pitfalls: HIGH - the current repo seams and the Python 3.11 requirement make the main failure modes explicit

**Research date:** 2026-03-24
**Valid until:** 2026-03-31
