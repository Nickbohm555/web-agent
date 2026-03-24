# Phase 1: Tool Contract Alignment - Research

**Researched:** 2026-03-24
**Domain:** Retrieval tool contract alignment across backend runtime, API/event contracts, frontend observability, and test surfaces
**Confidence:** HIGH

## User Constraints

No phase-specific `01-CONTEXT.md` exists.

Locked inputs from roadmap, requirements, project docs, and the user request:
- Keep `web_search` as the explicit search contract across quick, agentic, and deep-research modes.
- Align the page-opening contract to `open_url` across quick, agentic, and deep-research modes.
- Do not change retrieval behavior as part of this phase.
- Keep deep-research API response shape stable.
- Keep quick and agentic execution flow structurally intact; this phase is contract alignment, not architecture rewrite.
- Research must identify backend, frontend, API, test, and doc touchpoints.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TOOL-01 | User can access the search tool as `web_search` in quick, agentic, and deep-research modes. | Confirms `web_search` is already the active contract in runtime bindings, prompts, telemetry, and frontend schemas; plan should preserve it and add regression coverage. |
| TOOL-02 | User can access the page-opening or crawl tool as `open_url` in quick, agentic, and deep-research modes. | Identifies that the live codebase currently exposes `web_crawl`, not `web_extract`; recommends a behavior-preserving alias/rename to `open_url` with compatibility handling in runtime source extraction, telemetry schemas, prompts, and tests. |
</phase_requirements>

## Summary

Phase 1 is smaller and more mechanical than the roadmap wording suggests, but there is one important mismatch to plan around: this repository does not currently expose `web_extract` anywhere I could verify. The actual runtime contract today is `web_search` plus `web_crawl`. That pair is enforced in backend runtime constants, LangChain tool declarations, prompt text, source extraction logic, frontend run-event schemas, observability mapping, and a large test surface.

The safest implementation strategy is to treat Phase 1 as a contract rename from `web_crawl` to `open_url`, while keeping the underlying crawl pipeline, typed payloads, and retrieval-action semantics unchanged. `run_web_crawl(...)`, `WebCrawl*` schemas, and retrieval action type `open_page` should remain intact for now. Only the user-facing tool name should move to `open_url`, with temporary acceptance of both names in any backend parser that reads historical tool messages or mixed-version events.

Deep-research mode has two relevant surfaces today. The HTTP `/api/agent/run` path with `mode="deep_research"` is still a queued placeholder flow, but the shared runtime layer already has a `deep_research` profile that binds the same canonical tools as agentic mode. The plan should therefore verify both the queued API path and the runtime-level deep-research tool binding without trying to deliver the larger orchestration work that belongs to later phases.

**Primary recommendation:** Rename the canonical crawl tool exposure from `web_crawl` to `open_url`, preserve `run_web_crawl` internals, and make backend parsers temporarily accept both names so the contract changes without changing retrieval behavior.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | `0.115.12` | Backend HTTP route for `/api/agent/run` | Current backend API surface already depends on it. |
| LangChain | `0.3.27` | Agent construction and `@tool(...)` registration | Current runtime uses `create_agent`/fallback and named tools. |
| LangGraph | `0.6.11` | Runtime substrate for LangChain agent execution | Existing runtime already falls back to LangGraph prebuilt agent creation. |
| Pydantic Settings | `2.8.1` | Typed backend settings and contracts | Existing backend contracts and tool payload validation depend on typed models. |
| Zod | `4.3.6` | Frontend/API event contract validation | Frontend run-event schemas are Zod enums and object contracts. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Vitest | `4.1.0` | TypeScript contract and integration tests | Use for frontend/run-event schema and stream-history verification. |
| pytest | repo standard | Python runtime and tool tests | Use for backend canonical tool binding, route, and tool regression tests. |
| langchain-openai | `0.3.35` | Runtime model adapter | Present in the runtime factory path; not the focus of this phase. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Direct contract rename at every call site | Add `open_url` alias while keeping `web_crawl` internals | Lower behavior risk; lets tests and parsers migrate incrementally. |
| Renaming `run_web_crawl` and all schemas immediately | Keep `run_web_crawl`/`WebCrawl*` internals for now | Avoids wide mechanical churn in a contract-only phase. |
| Changing retrieval action type to `open_url` too | Keep retrieval action type as `open_page` | Frontend event semantics already distinguish tool name from user-visible action type. |

**Installation:**
```bash
npm install
python -m pip install -r backend/requirements.txt
```

**Version verification:** Versions above are the repo-pinned versions from [backend/requirements.txt](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/requirements.txt) and [package.json](/Users/nickbohm/Desktop/Tinkering/web-agent/package.json). For this phase, repo compatibility matters more than upgrading to latest.

## Architecture Patterns

### Recommended Project Structure
```text
backend/
├── agent/                  # Runtime binding, prompts, source extraction, mode routing
├── api/                    # FastAPI route/service contracts
└── app/tools/              # LangChain tool declarations and typed crawl/search payloads

src/
├── core/telemetry/         # Canonical event derivation from tool names
├── frontend/contracts*     # Zod run-event contracts
├── frontend/routes/        # API-facing route/event normalization
└── tests/                  # Contract/integration coverage for event schemas and UI state
```

### Pattern 1: Separate user-facing tool name from underlying crawl implementation
**What:** Keep `run_web_crawl(...)`, `WebCrawlInput`, `WebCrawlSuccess`, and crawl extraction internals stable, but expose the LangChain tool itself as `open_url`.
**When to use:** When the contract needs alignment without changing fetch/crawl behavior or payload shape.
**Example:**
```python
# Source: repo pattern adapted from backend/app/tools/web_crawl.py and LangChain tools docs
from langchain_core.tools import tool

def run_web_crawl(*, url: str | None = None, urls: list[str] | None = None, objective: str | None = None):
    ...

def build_open_url_tool(...):
    @tool("open_url", args_schema=WebCrawlInput)
    def open_url(
        url: str | None = None,
        urls: list[str] | None = None,
        objective: str | None = None,
    ) -> WebCrawlToolResult:
        return run_web_crawl(url=url, urls=urls, objective=objective, ...)

    return open_url
```

### Pattern 2: Keep canonical runtime binding centralized
**What:** Change the single source of truth in runtime binding code and make all profile/tool assertions depend on it.
**When to use:** Whenever tool names are part of a cross-mode runtime contract.
**Example:**
```python
# Source: backend/agent/runtime_constants.py + backend/agent/runtime_execution.py
CANONICAL_TOOL_NAMES = ("web_search", "open_url")

def get_canonical_tools() -> tuple[Any, Any]:
    return (web_search, open_url)

def assert_canonical_tool_names(tools: tuple[Any, ...]) -> None:
    actual_names = tuple(getattr(tool, "name", None) for tool in tools)
    if actual_names != CANONICAL_TOOL_NAMES:
        raise ValueError(...)
```

### Pattern 3: Be backward-tolerant at parse boundaries
**What:** During the rename, parsers that consume tool messages or event payloads should accept both `web_crawl` and `open_url`.
**When to use:** Any place that reads emitted tool names rather than generating them.
**Example:**
```python
# Source: repo pattern adapted from backend/agent/runtime_sources.py
ACCEPTED_CRAWL_TOOL_NAMES = {"web_crawl", "open_url"}

def is_crawl_tool_name(name: str | None) -> bool:
    return name in ACCEPTED_CRAWL_TOOL_NAMES
```

### Anti-Patterns to Avoid
- **Full crawl-domain rename in Phase 1:** Do not rename `WebCrawl*` models, modules, and internal helper names unless the plan explicitly budgets for that churn.
- **Changing retrieval actions and tool names together:** `open_page` is an observability/action concept, not the tool contract itself.
- **Touching deep-research orchestration now:** Keep this phase limited to contract exposure, runtime/tool bindings, and verification.
- **Only renaming prompts:** Prompt text is necessary but insufficient; runtime assertions, schemas, parsers, and tests are the real contract surface.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Tool registration | Custom tool-dispatch registry for simple static tools | LangChain `@tool("name", args_schema=...)` | Tool name is already first-class and officially supported. |
| Event contract parsing | Stringly typed ad hoc JSON parsing in frontend | Existing Zod `RunEventToolNameSchema` and browser contract parsers | Existing schemas already enforce exact tool names across UI surfaces. |
| Crawl behavior split | New `open_url` fetch pipeline | Existing `run_web_crawl(...)` pipeline | Requirement says align names without changing retrieval behavior. |
| Runtime tool compatibility | One-off special cases per mode | Shared `CANONICAL_TOOL_NAMES` and runtime binding helpers | Quick, agentic, and runtime deep-research already share this binding layer. |

**Key insight:** This phase should rename the contract, not the retrieval subsystem.

## Runtime State Inventory

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None verified. Deep-research jobs are in-memory only in [deep_research_store.py](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/agent/deep_research_store.py), and I found no persisted database or file artifact storing `web_extract`, `web_crawl`, or `open_url` as a key. | Code edit only. No data migration identified. |
| Live service config | None verified. I found no exported workflow/config files for external services that register these tool names outside git. | None. |
| OS-registered state | None verified. No launchd/systemd/pm2/task-scheduler registrations were found in repo context for these tool names. | None. |
| Secrets/env vars | None verified. Existing secrets are provider keys like `SERPER_API_KEY` and `OPENAI_API_KEY`; they do not encode the tool contract name. | None. |
| Build artifacts | None verified. No generated artifact in repo appears to cache `web_crawl` or `web_extract` as an installed package name. Local rebuild/test reruns are sufficient. | Code edit only. Re-run tests after rename. |

## Common Pitfalls

### Pitfall 1: Planning for `web_extract` when the live code uses `web_crawl`
**What goes wrong:** The plan targets the roadmap wording instead of the repo reality and misses the real rename surface.
**Why it happens:** `web_extract` appears in roadmap text, but not in current code.
**How to avoid:** Start the implementation plan with a confirmed finding: the live rename is `web_crawl` -> `open_url`.
**Warning signs:** `rg "web_extract"` returns no code matches while tests still fail on `web_crawl`.

### Pitfall 2: Renaming emitted tool names but not accepted parser names
**What goes wrong:** New runs emit `open_url`, but historical or mixed-version payload readers reject or ignore them.
**Why it happens:** Parser surfaces are easy to miss, especially `runtime_sources.py` and frontend run-event schemas.
**How to avoid:** Update emitters and parsers in the same plan wave, and accept both names in backend parsers during transition.
**Warning signs:** Source extraction drops crawl citations or frontend event parsing rejects `tool_name`.

### Pitfall 3: Renaming retrieval action semantics unnecessarily
**What goes wrong:** `open_page` gets changed even though the requirement is about tool naming, creating unnecessary frontend churn.
**Why it happens:** Tool name and retrieval action are related but distinct.
**How to avoid:** Keep retrieval action type as `open_page` unless the user explicitly wants a second contract rename.
**Warning signs:** Timeline/state tests fail on `action_type: "open_page"` with no requirement benefit.

### Pitfall 4: Verifying only agentic mode
**What goes wrong:** Quick mode still works via direct runners, but deep-research runtime or frontend contracts remain stale.
**Why it happens:** The rename surface spans separate quick runtime, shared runtime profiles, API queuing, and frontend event schemas.
**How to avoid:** Plan verification per surface: quick runtime, agentic runtime, deep-research runtime/profile, frontend contracts, and route/event observability.
**Warning signs:** Backend unit tests pass, but frontend contract tests or run-history integrations fail.

## Code Examples

Verified patterns from repo and official sources:

### Named tool registration is the contract seam
```python
# Source: https://docs.langchain.com/oss/python/langchain/tools
from langchain.tools import tool

@tool
def search_database(query: str, limit: int = 10) -> str:
    """Search the customer database for records matching the query."""
    ...
```

```python
# Source: backend/app/tools/web_search.py
@tool("web_search", args_schema=WebSearchInput)
def bounded_web_search(query: str, max_results: int = 5) -> WebSearchToolResult:
    ...
```

```python
# Source: backend/app/tools/web_crawl.py
@tool("web_crawl", args_schema=WebCrawlInput)
def bounded_web_crawl(
    url: str | None = None,
    urls: list[str] | None = None,
    objective: str | None = None,
) -> WebCrawlToolResult:
    ...
```

### Runtime binding already centralizes cross-mode tool exposure
```python
# Source: backend/agent/runtime_execution.py
def get_canonical_tools() -> tuple[Any, Any]:
    return (web_search, web_crawl)

def get_tools_for_profile(...):
    if profile.name == QUICK_RUNTIME_MODE:
        return get_canonical_tools()
    return (
        build_web_search_tool(...),
        build_web_crawl_tool(...),
    )
```

### Frontend contract parsing is exact-name sensitive
```ts
// Source: src/frontend/contracts.ts
export const RunEventToolNameSchema = z.enum(["web_search", "web_crawl"]);
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Generic or implicit tool naming in prompts | Explicit named LangChain tools bound into `create_agent` | Current repo state; LangChain docs currently emphasize named tool registration | Tool name drift is a contract issue, not just prompt wording. |
| Treating crawl as a backend implementation detail | Exposing crawl/open as an explicit tool name plus `open_page` retrieval action | Current repo state | User-facing naming must be consistent across runtime and observability. |
| Building simpler research flows with `create_agent` | Deep Agents for later multi-step planning/subagent workflows | Current Deep Agents docs | Phase 1 should not attempt to implement Deep Agents; only align the tool contract those later phases will depend on. |

**Deprecated/outdated:**
- Planning against `web_extract`: outdated for this repo state; no verified code surface currently uses that name.

## Open Questions

1. **Should Phase 1 preserve a temporary `web_crawl` compatibility alias for emitted tool names, or only for parsers?**
   - What we know: runtime parsers and frontend schemas are exact-name sensitive today.
   - What's unclear: whether Nicholas wants immediate hard cutover or one-phase backward compatibility.
   - Recommendation: emit only `open_url`, but let backend parsers accept both names during the transition.

2. **Should frontend public fetch routes eventually expose `open_url` too, or stay as route/path-level `fetch` while only telemetry/tool contracts change?**
   - What we know: frontend Express fetch route currently emits telemetry as `web_crawl`.
   - What's unclear: whether external HTTP endpoint naming is in scope for this phase.
   - Recommendation: treat route paths as out of scope unless explicitly required; focus on tool/event contracts.

3. **Do we want a follow-up cleanup phase to rename internal `WebCrawl*` schemas and modules after contract alignment lands?**
   - What we know: internal crawl naming is pervasive and stable.
   - What's unclear: whether full terminology cleanup is worth the churn now.
   - Recommendation: defer full internal rename unless Nicholas wants terminology consistency over minimal-risk delivery.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | `pytest` + `vitest@4.1.0` |
| Config file | `package.json` for Vitest; pytest uses repo defaults in `backend/tests/` |
| Quick run command | `python -m pytest backend/tests/agent/test_runtime.py backend/tests/tools/test_web_crawl_tool.py -q` |
| Full suite command | `python -m pytest backend/tests -q && npm test -- --runInBand` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TOOL-01 | `web_search` remains the explicit tool name in quick, agentic, and deep-research runtime surfaces | unit/integration | `python -m pytest backend/tests/agent/test_runtime.py -q` | ✅ |
| TOOL-02 | page-open tool is exposed as `open_url` across runtime, event contracts, and frontend parsing | unit/contract/integration | `python -m pytest backend/tests/agent/test_runtime.py backend/tests/tools/test_web_crawl_tool.py -q && npm test -- src/tests/frontend-api/run-events.contracts.test.ts src/tests/frontend-api/observability-correlation.test.ts src/tests/frontend-api/run-history.integration.test.ts src/tests/frontend-api/runs.stream.test.ts src/tests/frontend/state.test.ts src/tests/frontend/timeline.test.ts` | ✅ |

### Sampling Rate
- **Per task commit:** `python -m pytest backend/tests/agent/test_runtime.py backend/tests/tools/test_web_crawl_tool.py -q`
- **Per wave merge:** `npm test -- src/tests/frontend-api/run-events.contracts.test.ts src/tests/frontend-api/observability-correlation.test.ts src/tests/frontend-api/run-history.integration.test.ts src/tests/frontend-api/runs.stream.test.ts src/tests/frontend/state.test.ts src/tests/frontend/timeline.test.ts`
- **Phase gate:** `python -m pytest backend/tests -q && npm test`

### Wave 0 Gaps
- [ ] Add or update backend tests that assert `CANONICAL_TOOL_NAMES == ("web_search", "open_url")`.
- [ ] Add parser-level backend tests proving source extraction accepts `open_url` and, if chosen, legacy `web_crawl`.
- [ ] Update frontend Zod/browser contract tests for `tool_name: "open_url"`.
- [ ] Add one end-to-end event normalization test proving `open_url` still derives retrieval action `open_page`.

## Sources

### Primary (HIGH confidence)
- Repo audit via [runtime_execution.py](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/agent/runtime_execution.py), [runtime_constants.py](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/agent/runtime_constants.py), [web_search.py](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/app/tools/web_search.py), [web_crawl.py](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/app/tools/web_crawl.py), [runtime_sources.py](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/agent/runtime_sources.py)
- Repo audit via [contracts.ts](/Users/nickbohm/Desktop/Tinkering/web-agent/src/frontend/contracts.ts), [browser-contracts.ts](/Users/nickbohm/Desktop/Tinkering/web-agent/src/frontend/client/browser-contracts.ts), [runs.ts](/Users/nickbohm/Desktop/Tinkering/web-agent/src/frontend/routes/runs.ts), [state.ts](/Users/nickbohm/Desktop/Tinkering/web-agent/src/frontend/client/state.ts), [observability-logger.ts](/Users/nickbohm/Desktop/Tinkering/web-agent/src/core/telemetry/observability-logger.ts)
- Repo audit via [test_runtime.py](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/tests/agent/test_runtime.py), [test_web_crawl_tool.py](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/tests/tools/test_web_crawl_tool.py), [run-events.contracts.test.ts](/Users/nickbohm/Desktop/Tinkering/web-agent/src/tests/frontend-api/run-events.contracts.test.ts), [observability-correlation.test.ts](/Users/nickbohm/Desktop/Tinkering/web-agent/src/tests/frontend-api/observability-correlation.test.ts)
- LangChain tools docs: https://docs.langchain.com/oss/python/langchain/tools
- LangChain agents docs: https://docs.langchain.com/oss/python/langchain/agents
- Deep Agents overview: https://docs.langchain.com/oss/python/deepagents/overview

### Secondary (MEDIUM confidence)
- [ROADMAP.md](/Users/nickbohm/Desktop/Tinkering/web-agent/.planning/ROADMAP.md) for the stated `web_extract` -> `open_url` intent, cross-checked against code.

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - repo-pinned versions and active runtime/test files make the stack clear.
- Architecture: HIGH - the rename surface is explicit in runtime bindings, prompt text, frontend schemas, and telemetry.
- Pitfalls: HIGH - backed by verified code paths and exact-name parser/test surfaces.

**Research date:** 2026-03-24
**Valid until:** 2026-04-23
