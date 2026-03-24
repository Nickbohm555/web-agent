# OpenAI Web Search Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the current run modes into three real product behaviors: deterministic quick search with one final model call, bounded agentic search, and several-minute deep research with background orchestration.

**Architecture:** Keep one run API concept, but route `quick`, `agentic`, and `deep_research` into different runtime paths. Build `quick` as direct function orchestration over the existing retrieval tools, preserve the current bounded agent loop for `agentic`, and move `deep_research` onto a dedicated persisted background workflow instead of treating it as a bigger synchronous profile.

**Tech Stack:** Python, FastAPI, Pydantic, LangChain/LangGraph tool entrypoints, OpenAI API, pytest, TypeScript, Express, Vitest

---

## File Structure

**Create:**
- `backend/agent/quick_runtime.py` - Explicit quick-mode orchestration entrypoint.
- `backend/agent/quick_selection.py` - Deterministic top-result filtering and fanout selection.
- `backend/agent/quick_evidence.py` - Evidence bundle assembly from crawled pages.
- `backend/agent/answer_synthesis.py` - One-shot structured answer generation over bundled evidence.
- `backend/agent/deep_research_runtime.py` - Background research job coordinator.
- `backend/agent/deep_research_planning.py` - Sub-question and research-objective planning.
- `backend/agent/deep_research_execution.py` - Multi-wave search/crawl execution.
- `backend/agent/deep_research_verification.py` - Conflict checks and follow-up verification logic.
- `backend/agent/deep_research_store.py` - In-memory or persisted job state access layer with explicit typed records.
- `backend/agent/schemas/quick_answer.py` - Quick answer synthesis request/result models if they are shared across modules.
- `backend/agent/schemas/deep_research.py` - Deep-research job, stage, and progress models.
- `backend/tests/agent/test_quick_runtime.py` - Quick pipeline tests.
- `backend/tests/agent/test_answer_synthesis.py` - Final synthesis unit tests.
- `backend/tests/agent/test_deep_research_runtime.py` - Deep-research orchestration tests.
- `backend/tests/api/test_agent_run_service.py` - Service-level mode routing and background behavior tests.

**Modify:**
- `backend/agent/runtime_execution.py` - Route modes into explicit quick vs agentic vs deep-research paths.
- `backend/agent/runtime_constants.py` - Reduce quick to orchestration-only config, preserve agentic profile, redefine deep-research profile shape if needed.
- `backend/agent/runtime.py` - Re-export updated runtime entrypoints only.
- `backend/agent/schemas/__init__.py` - Export any new typed runtime/job schemas.
- `backend/api/services/agent_run.py` - Support synchronous completed runs for `quick`/`agentic` and queued/background responses for `deep_research`.
- `backend/api/routes/agent_run.py` - Update route response models and execution-surface headers.
- `backend/api/schemas/agent_run.py` - Add typed queued/running response shapes for deep research while preserving completed responses.
- `backend/api/schemas/__init__.py` - Export updated response models.
- `backend/api/errors.py` - Add any new background-run error mappings if needed.
- `backend/tests/agent/test_runtime.py` - Update mode-routing expectations and keep agentic regression coverage.
- `backend/tests/api/test_agent_run_route.py` - Cover mixed sync/background mode responses.
- `src/frontend/contracts.ts` - Accept updated backend run-start / run-result contracts.
- `src/frontend/routes/runs.ts` - Handle several-minute deep-research lifecycle and avoid assuming synchronous completion from backend.
- `src/tests/frontend-api/run-history.integration.test.ts` - Add background deep-research lifecycle assertions.
- `public/index.html` - Update mode copy only if it no longer matches runtime behavior.

**Reference While Implementing:**
- `docs/superpowers/specs/2026-03-23-openai-web-search-parity-design.md`
- `backend/agent/runtime_execution.py`
- `backend/agent/quick_search.py`
- `backend/app/tools/web_search.py`
- `backend/app/tools/web_crawl.py`
- `backend/api/services/agent_run.py`
- `backend/api/routes/agent_run.py`
- `backend/api/schemas/agent_run.py`
- `src/frontend/routes/runs.ts`

### Task 1: Lock the New Mode Contracts and Runtime Split

**Files:**
- Modify: `backend/agent/runtime_execution.py`
- Modify: `backend/agent/runtime_constants.py`
- Modify: `backend/agent/runtime.py`
- Modify: `backend/agent/schemas/__init__.py`
- Modify: `backend/api/schemas/agent_run.py`
- Modify: `backend/api/schemas/__init__.py`
- Test: `backend/tests/agent/test_runtime.py`
- Test: `backend/tests/api/test_agent_run_route.py`

- [ ] **Step 1: Write the failing mode-contract tests**

```python
def test_run_agent_once_routes_quick_mode_into_quick_runtime() -> None:
    quick_result = AgentRunResult(
        run_id="run-quick",
        status="completed",
        final_answer={"text": "Quick answer"},
        sources=[],
        tool_call_count=4,
        elapsed_ms=12,
    )
    deps = RuntimeDependencies(
        quick_runtime_runner=lambda **_: quick_result,
        agent=RaisingStubAgent(RuntimeError("agent path should not run")),
    )
    result = run_agent_once("Find pricing", "quick", runtime_dependencies=deps)
    assert result.run_id == "run-quick"


def test_agent_run_request_accepts_background_deep_research_response_shape() -> None:
    payload = AgentRunQueuedResponse(
        run_id="run-deep",
        status="queued",
        metadata=AgentRunQueuedMetadata(execution_surface="background"),
    )
    assert payload.status == "queued"
```

- [ ] **Step 2: Run the focused tests and confirm they fail**

Run: `pytest backend/tests/agent/test_runtime.py -k "quick_runtime or background_deep_research" -v`
Expected: FAIL because the runtime dependencies and queued response models do not exist yet.

- [ ] **Step 3: Add explicit runtime seams instead of overloading the agent path**

```python
@dataclass(frozen=True)
class RuntimeDependencies:
    agent: AgentExecutor | None = None
    agent_factory: AgentFactory | None = None
    quick_search_runner: QuickSearchRunner | None = None
    quick_runtime_runner: QuickRuntimeRunner | None = None
    deep_research_runner: DeepResearchRunner | None = None


if profile.name == "quick":
    return run_quick_runtime(...)
if profile.name == "deep_research":
    return run_deep_research(...)
return run_agentic_runtime(...)
```

Run: keep `quick`, `agentic`, and `deep_research` on separate code paths in `runtime_execution.py`; do not hide them behind a generic callable registry.
Expected: the runtime entrypoint reflects three distinct execution shapes.

- [ ] **Step 4: Add typed API response models for sync-complete vs background-queued runs**

```python
class AgentRunQueuedMetadata(BaseModel):
    execution_surface: Literal["background"]


class AgentRunQueuedResponse(BaseModel):
    run_id: str
    status: Literal["queued", "running"]
    metadata: AgentRunQueuedMetadata
```

Run: update the route schema layer so deep research can return a typed queued/running response without pretending every request completes synchronously.
Expected: backend contracts match the approved design before deeper implementation begins.

- [ ] **Step 5: Run the mode-contract tests again**

Run: `pytest backend/tests/agent/test_runtime.py -k "quick_runtime or background_deep_research" -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/agent/runtime_execution.py \
  backend/agent/runtime_constants.py \
  backend/agent/runtime.py \
  backend/agent/schemas/__init__.py \
  backend/api/schemas/agent_run.py \
  backend/api/schemas/__init__.py \
  backend/tests/agent/test_runtime.py \
  backend/tests/api/test_agent_run_route.py
git commit -m "feat: split run mode contracts by execution path"
```

### Task 2: Build Quick Mode as a Deterministic Retrieval Pipeline

**Files:**
- Create: `backend/agent/quick_runtime.py`
- Create: `backend/agent/quick_selection.py`
- Create: `backend/agent/quick_evidence.py`
- Modify: `backend/agent/runtime_execution.py`
- Modify: `backend/agent/runtime_constants.py`
- Test: `backend/tests/agent/test_quick_runtime.py`
- Test: `backend/tests/agent/test_runtime.py`

- [ ] **Step 1: Write the failing quick-pipeline tests**

```python
def test_run_quick_runtime_searches_once_crawls_top_three_and_returns_sources() -> None:
    result = run_quick_runtime(
        prompt="What is the pricing?",
        retrieval_policy=AgentRunRetrievalPolicy(),
        search_runner=stub_search_runner,
        crawl_runner=stub_crawl_runner,
        answer_runner=stub_answer_runner,
    )
    assert stub_search_runner.calls == 1
    assert stub_crawl_runner.requested_urls == [
        "https://example.com/1",
        "https://example.com/2",
        "https://example.com/3",
    ]
    assert result.status == "completed"


def test_run_quick_runtime_skips_disallowed_or_duplicate_urls() -> None:
    selected = select_quick_urls(search_response, max_urls=3, retrieval_policy=policy)
    assert selected == ["https://allowed.example.com/a", "https://allowed.example.com/b"]


def test_run_quick_runtime_returns_failure_when_all_crawls_fail() -> None:
    result = run_quick_runtime(...)
    assert result.status == "failed"
    assert result.error.category == "tool_failure"
```

- [ ] **Step 2: Run the quick-runtime tests and confirm they fail**

Run: `pytest backend/tests/agent/test_quick_runtime.py -v`
Expected: FAIL because the quick-runtime modules do not exist yet.

- [ ] **Step 3: Implement deterministic result selection**

```python
def select_quick_urls(
    response: WebSearchResponse,
    *,
    retrieval_policy: AgentRunRetrievalPolicy,
    max_urls: int = 3,
) -> list[str]:
    seen: set[str] = set()
    selected: list[str] = []
    for result in response.results:
        url = str(result.url)
        if url in seen:
            continue
        if not is_url_allowed(url, **domain_scope_kwargs(retrieval_policy.search)):
            continue
        seen.add(url)
        selected.append(url)
        if len(selected) == max_urls:
            break
    return selected
```

Run: keep selection logic isolated in `quick_selection.py` so tests do not need the whole runtime to verify URL picking behavior.
Expected: top-result fanout is deterministic and policy-aware.

- [ ] **Step 4: Implement the quick orchestration path**

```python
def run_quick_runtime(...) -> AgentRunResult:
    search_payload = run_quick_search(...)
    search_response = WebSearchResponse.model_validate(search_payload)
    urls = select_quick_urls(search_response, retrieval_policy=retrieval_policy)
    crawl_payloads = [crawl_runner(url=url, objective=prompt) for url in urls]
    evidence = build_quick_evidence(prompt=prompt, search_response=search_response, crawl_payloads=crawl_payloads)
    return answer_runner(prompt=prompt, evidence=evidence, ...)
```

Run: call concrete functions directly in sequence. Do not send quick mode through the LangChain agent or generic tool loop.
Expected: quick mode becomes a fixed orchestration pipeline rather than snippet-only synthesis.

- [ ] **Step 5: Run the quick tests again**

Run: `pytest backend/tests/agent/test_quick_runtime.py backend/tests/agent/test_runtime.py -k "quick" -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/agent/quick_runtime.py \
  backend/agent/quick_selection.py \
  backend/agent/quick_evidence.py \
  backend/agent/runtime_execution.py \
  backend/agent/runtime_constants.py \
  backend/tests/agent/test_quick_runtime.py \
  backend/tests/agent/test_runtime.py
git commit -m "feat: add deterministic quick retrieval pipeline"
```

### Task 3: Add the One-Shot Quick Answer Synthesis Layer

**Files:**
- Create: `backend/agent/answer_synthesis.py`
- Create: `backend/agent/schemas/quick_answer.py`
- Modify: `backend/agent/quick_runtime.py`
- Modify: `backend/agent/schemas/__init__.py`
- Test: `backend/tests/agent/test_answer_synthesis.py`
- Test: `backend/tests/agent/test_quick_runtime.py`

- [ ] **Step 1: Write the failing answer-synthesis tests**

```python
def test_build_quick_answer_prompt_includes_question_evidence_and_source_ids() -> None:
    prompt = build_quick_answer_prompt(
        question="What is the refund policy?",
        evidence=QuickEvidenceBundle(
            sources=[
                QuickEvidenceSource(source_id="src-1", title="Refunds", url="https://example.com/refunds", excerpt="30-day refund policy"),
            ]
        ),
    )
    assert "What is the refund policy?" in prompt
    assert "src-1" in prompt
    assert "30-day refund policy" in prompt


def test_synthesize_quick_answer_returns_structured_answer_and_sources() -> None:
    result = synthesize_quick_answer(...)
    assert result.final_answer.text == "Customers can request a refund within 30 days."
    assert result.sources[0].source_id == "src-1"
```

- [ ] **Step 2: Run the synthesis tests and confirm they fail**

Run: `pytest backend/tests/agent/test_answer_synthesis.py -v`
Expected: FAIL because the synthesis module and quick answer schemas do not exist yet.

- [ ] **Step 3: Add typed quick-evidence and synthesis schemas**

```python
class QuickEvidenceSource(BaseModel):
    source_id: str
    title: str
    url: HttpUrl
    excerpt: str


class QuickEvidenceBundle(BaseModel):
    question: str
    sources: list[QuickEvidenceSource]
```

Run: put synthesis-specific models in `backend/agent/schemas/quick_answer.py` rather than adding loose dicts to runtime code.
Expected: the final answer stage has a stable typed contract.

- [ ] **Step 4: Implement the one-shot answer synthesis**

```python
def synthesize_quick_answer(...) -> AgentRunResult:
    completion = client.responses.create(
        model=model,
        input=build_quick_answer_prompt(...),
    )
    structured_answer = AgentStructuredAnswer(text=completion.output_text.strip())
    return AgentRunResult(
        run_id=run_id,
        status="completed",
        final_answer=structured_answer,
        sources=sources,
        tool_call_count=tool_call_count,
        elapsed_ms=elapsed_ms(started_at),
    )
```

Run: keep this as one direct model call. LangChain is acceptable only if used as a thin structured-output wrapper, not as an agent or tool loop.
Expected: quick mode uses retrieved page evidence and one final LLM synthesis pass.

- [ ] **Step 5: Run the quick-answer tests again**

Run: `pytest backend/tests/agent/test_answer_synthesis.py backend/tests/agent/test_quick_runtime.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/agent/answer_synthesis.py \
  backend/agent/schemas/quick_answer.py \
  backend/agent/quick_runtime.py \
  backend/agent/schemas/__init__.py \
  backend/tests/agent/test_answer_synthesis.py \
  backend/tests/agent/test_quick_runtime.py
git commit -m "feat: add one-shot quick answer synthesis"
```

### Task 4: Preserve Agentic Mode and Refactor Only What Deep Research Needs

**Files:**
- Modify: `backend/agent/runtime_execution.py`
- Modify: `backend/agent/prompts.py`
- Modify: `backend/tests/agent/test_runtime.py`
- Test: `backend/tests/agent/test_runtime.py`

- [ ] **Step 1: Write the failing regression tests for unchanged agentic behavior**

```python
def test_agentic_mode_still_uses_agent_factory_and_profile_tool_limits() -> None:
    factory = CapturingAgentFactory(raw_result={"output": "Answer"})
    result = run_agent_once(
        "Compare two providers",
        "agentic",
        runtime_dependencies=RuntimeDependencies(agent_factory=factory),
    )
    assert result.status == "completed"
    assert factory.captured_profile.name == "agentic"
    assert factory.captured_tools is not None


def test_deep_research_no_longer_reuses_agentic_prompt_appendix_only() -> None:
    prompt = build_system_prompt(profile=get_runtime_profile("deep_research"), retrieval_brief="...")
    assert "Work methodically" in prompt
```

- [ ] **Step 2: Run the regression tests and confirm any failures**

Run: `pytest backend/tests/agent/test_runtime.py -k "agentic_mode_still_uses_agent_factory or deep_research_no_longer" -v`
Expected: FAIL if the runtime split accidentally regresses the current agentic path.

- [ ] **Step 3: Refactor the shared runtime wiring without changing agentic semantics**

```python
def run_agentic_runtime(...) -> AgentRunResult:
    agent = resolve_agent(...)
    raw_result = agent.invoke(...)
    return normalize_agent_result(...)
```

Run: isolate the existing agent path into an `agentic`-specific function so deep research can diverge without growing more flags inside one function.
Expected: agentic remains stable and readable while quick/deep paths move elsewhere.

- [ ] **Step 4: Run the full runtime regression set**

Run: `pytest backend/tests/agent/test_runtime.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/agent/runtime_execution.py \
  backend/agent/prompts.py \
  backend/tests/agent/test_runtime.py
git commit -m "refactor: isolate bounded agentic runtime path"
```

### Task 5: Build Deep Research as a Background Job Workflow

**Files:**
- Create: `backend/agent/deep_research_runtime.py`
- Create: `backend/agent/deep_research_planning.py`
- Create: `backend/agent/deep_research_execution.py`
- Create: `backend/agent/deep_research_verification.py`
- Create: `backend/agent/deep_research_store.py`
- Create: `backend/agent/schemas/deep_research.py`
- Modify: `backend/api/services/agent_run.py`
- Modify: `backend/api/routes/agent_run.py`
- Modify: `backend/api/schemas/agent_run.py`
- Modify: `backend/api/errors.py`
- Modify: `src/frontend/contracts.ts`
- Modify: `src/frontend/routes/runs.ts`
- Modify: `src/tests/frontend-api/run-history.integration.test.ts`
- Modify: `public/index.html`
- Test: `backend/tests/agent/test_deep_research_runtime.py`
- Test: `backend/tests/api/test_agent_run_service.py`
- Test: `backend/tests/api/test_agent_run_route.py`
- Test: `src/tests/frontend-api/run-history.integration.test.ts`

- [ ] **Step 1: Write the failing deep-research lifecycle tests**

```python
def test_start_deep_research_returns_queued_response_and_persists_job() -> None:
    response = execute_agent_run_request(
        AgentRunRequest(prompt="Investigate market share", mode="deep_research")
    )
    assert response.status_code == 202


def test_deep_research_runtime_plans_then_executes_waves_then_marks_complete() -> None:
    store = InMemoryDeepResearchStore()
    job = start_deep_research(...)
    run_deep_research_job(job.job_id, store=store, ...)
    saved = store.get(job.job_id)
    assert saved.stage == "completed"
    assert saved.wave_count >= 1
```

```ts
it("keeps deep research runs active across background progress and completion", async () => {
  const start = await harness.postJson("/api/runs", {
    prompt: "Investigate deep research",
    mode: "deep_research",
  });
  expect(start.status).toBe(201);
  const runId = parseRunId(start.json);
  const events = await harness.getText(`/api/runs/${runId}/events`);
  expect(events.body).toContain("event: run_status");
  expect(events.body).toContain("event: run_complete");
});
```

- [ ] **Step 2: Run the lifecycle tests and confirm they fail**

Run: `pytest backend/tests/agent/test_deep_research_runtime.py backend/tests/api/test_agent_run_service.py backend/tests/api/test_agent_run_route.py -v`
Run: `npm run test -- src/tests/frontend-api/run-history.integration.test.ts`
Expected: FAIL because deep-research background orchestration and response contracts are not implemented yet.

- [ ] **Step 3: Add typed deep-research job models and store**

```python
class DeepResearchStage(str, Enum):
    QUEUED = "queued"
    PLANNING = "planning"
    SEARCHING = "searching"
    VERIFYING = "verifying"
    SYNTHESIZING = "synthesizing"
    COMPLETED = "completed"
    FAILED = "failed"


class DeepResearchJob(BaseModel):
    job_id: str
    prompt: str
    stage: DeepResearchStage
    sub_questions: list[str] = Field(default_factory=list)
    sources: list[AgentSourceReference] = Field(default_factory=list)
```

Run: keep deep-research state typed in `backend/agent/schemas/deep_research.py` and accessed through a focused store module rather than leaking ad hoc dicts through services.
Expected: the background runtime has a stable persisted state model.

- [ ] **Step 4: Implement the background orchestration flow**

```python
def start_deep_research(...) -> AgentRunQueuedResponse:
    job = initialize_job(...)
    store.save(job)
    schedule_job(job.job_id)
    return AgentRunQueuedResponse(...)


def run_deep_research_job(job_id: str, ...) -> None:
    job = store.get_required(job_id)
    plan = build_deep_research_plan(job.prompt, ...)
    job = execute_research_waves(job, plan, ...)
    job = verify_research_claims(job, ...)
    job = finalize_research_answer(job, ...)
    store.save(job)
```

Run: support several-minute execution and persist progress between stages. Do not force deep research through the synchronous request-response path.
Expected: deep research becomes a true background workflow.

- [ ] **Step 5: Wire backend route/service behavior to mixed sync and background responses**

```python
if payload.mode == "deep_research":
    queued = start_deep_research_request(payload)
    return JSONResponse(status_code=202, content=queued.model_dump())
return AgentRunSuccessResponse.from_run_result(...)
```

Run: update headers and route logic so `x-run-execution-surface` accurately reflects `background` for deep research.
Expected: backend execution semantics are truthful and typed.

- [ ] **Step 6: Update frontend contracts and history flow**

```ts
export const BackendAgentRunQueuedResponseSchema = z.object({
  run_id: z.string().min(1),
  status: z.enum(["queued", "running"]),
  metadata: z.object({
    execution_surface: z.literal("background"),
  }).strict(),
}).strict();
```

Run: adjust `src/frontend/contracts.ts` and `src/frontend/routes/runs.ts` so deep research can remain active for several minutes without assuming immediate completion from the backend.
Expected: UI and history handling match the background runtime.

- [ ] **Step 7: Run the deep-research verification set**

Run: `pytest backend/tests/agent/test_deep_research_runtime.py backend/tests/api/test_agent_run_service.py backend/tests/api/test_agent_run_route.py -v`
Run: `npm run test -- src/tests/frontend-api/run-history.integration.test.ts`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add backend/agent/deep_research_runtime.py \
  backend/agent/deep_research_planning.py \
  backend/agent/deep_research_execution.py \
  backend/agent/deep_research_verification.py \
  backend/agent/deep_research_store.py \
  backend/agent/schemas/deep_research.py \
  backend/api/services/agent_run.py \
  backend/api/routes/agent_run.py \
  backend/api/schemas/agent_run.py \
  backend/api/errors.py \
  backend/tests/agent/test_deep_research_runtime.py \
  backend/tests/api/test_agent_run_service.py \
  backend/tests/api/test_agent_run_route.py \
  src/frontend/contracts.ts \
  src/frontend/routes/runs.ts \
  src/tests/frontend-api/run-history.integration.test.ts \
  public/index.html
git commit -m "feat: add background deep research runtime"
```

### Task 6: Run Full Verification and Refresh Containers If Runtime Surfaces Changed

**Files:**
- Modify: any touched verification snapshots or docs only if commands require updates
- Test: `backend/tests/agent/test_runtime.py`
- Test: `backend/tests/agent/test_quick_runtime.py`
- Test: `backend/tests/agent/test_answer_synthesis.py`
- Test: `backend/tests/agent/test_deep_research_runtime.py`
- Test: `backend/tests/api/test_agent_run_route.py`
- Test: `backend/tests/api/test_agent_run_service.py`
- Test: `src/tests/frontend-api/run-history.integration.test.ts`

- [ ] **Step 1: Run the backend regression suite**

Run: `pytest backend/tests/agent/test_runtime.py backend/tests/agent/test_quick_runtime.py backend/tests/agent/test_answer_synthesis.py backend/tests/agent/test_deep_research_runtime.py backend/tests/api/test_agent_run_route.py backend/tests/api/test_agent_run_service.py -v`
Expected: PASS

- [ ] **Step 2: Run the frontend contract and history tests**

Run: `npm run test -- src/tests/frontend-api/run-history.integration.test.ts`
Expected: PASS

- [ ] **Step 3: Run broader repo validation**

Run: `npm run typecheck`
Run: `npm run test`
Expected: PASS

- [ ] **Step 4: Refresh affected containers**

Run: `docker compose restart backend frontend`
Expected: both services restart cleanly because runtime/service code changed.

If any `Dockerfile`, lockfile, or Python dependency manifest changed:
Run: `docker compose up --build -d backend frontend`
Expected: fresh images built and containers replaced.

- [ ] **Step 5: Commit any final test/docs adjustments**

```bash
git add -A
git commit -m "chore: verify web search parity runtime changes"
```

## Notes for Implementers

- Keep `quick` and `deep_research` out of the LangChain agent path.
- Preserve `agentic` semantics unless a failing regression test proves a necessary adjustment.
- Prefer feature-local `schemas/` files for any new typed model families.
- Keep deep-research modules small and single-purpose; do not let `runtime_execution.py` or one new deep-research file become monolithic.
- If the final synthesis layer needs OpenAI client injection for tests, inject that specific seam directly rather than introducing a generic runtime runner abstraction.
