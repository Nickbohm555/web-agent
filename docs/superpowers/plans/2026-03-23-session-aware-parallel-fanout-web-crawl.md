# Session-Aware Parallel Fan-Out Web Crawl Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade `web_crawl` into one final session-aware crawl tool that supports deterministic parallel fan-out for a selected batch of URLs while preserving typed results, source extraction, and backward compatibility for single-page calls.

**Architecture:** Keep one agent-facing `web_crawl` boundary and merge the approved session-aware and parallel fan-out designs into a single contract. Add focused batch schemas and orchestration modules, preserve the existing single-page extractor/fallback behavior, and extend runtime source handling so successful batch items become citations the same way single-page crawl successes do today.

**Tech Stack:** Python, Pydantic, LangChain/LangGraph tool entrypoints, httpx, Playwright-backed crawler modules, pytest

---

## File Structure

**Create:**
- `backend/app/tools/schemas/web_crawl_batch.py` - Batch input and ordered batch result models for `web_crawl`.
- `backend/app/tools/web_crawl_batch.py` - Deterministic parallel batch orchestration and result aggregation.
- `backend/app/crawler/schemas/session_profile.py` - Session profile models from the approved session-aware crawl design.
- `backend/app/crawler/schemas/browser_fetch.py` - Browser fetch result and seeded browser-state models.
- `backend/app/crawler/schemas/fetch_strategy.py` - Strategy decision and classification models.
- `backend/app/crawler/session_profiles.py` - Domain-matched session profile resolution.
- `backend/app/crawler/fetch_strategy.py` - Initial strategy and escalation decision logic.
- `backend/app/crawler/fetch_orchestrator.py` - Session-aware crawl orchestration for single-page execution.
- `backend/app/crawler/browser_worker.py` - Browser-backed rendered fetch execution.
- `backend/app/crawler/fetch_classification.py` - Classification helpers for blocked/auth/thin/challenge outcomes.
- `backend/app/crawler/content_normalizer.py` - Normalize HTTP/browser fetch outputs into extractor input.
- `backend/app/crawler/error_mapping.py` - Stable typed crawl error mapping.

**Modify:**
- `backend/app/tools/schemas/web_crawl.py` - Merge the final single/batch/session-aware public tool schemas.
- `backend/app/contracts/web_crawl.py` - Re-export the updated crawl contract types.
- `backend/app/tools/schemas/__init__.py` - Export new batch crawl schemas.
- `backend/app/contracts/__init__.py` - Export updated crawl contract types if needed.
- `backend/app/tools/web_crawl.py` - Single-vs-batch dispatch, final tool docstring, policy checks, and entrypoint wiring.
- `backend/app/tools/__init__.py` - Export updated crawl tool symbols if needed.
- `backend/agent/runtime_sources.py` - Flatten successful batch crawl items into runtime sources/citations.
- `backend/agent/prompts.py` - Instruct the agent to batch selected URL opens with `web_crawl`.
- `backend/tests/tools/test_web_crawl_tool.py` - Expand tool tests for final combined single/batch behavior.
- `backend/tests/agent/test_runtime.py` - Add runtime/source-registry coverage for batch crawl results.
- `backend/tests/crawler/test_http_worker.py` - Adjust only if shared fetch models change.
- `backend/tests/crawler/` new or existing test modules - Add session-profile, strategy, browser, and orchestrator tests.

**Reference While Implementing:**
- `docs/superpowers/specs/2026-03-23-session-aware-web-crawl-design.md`
- `docs/superpowers/specs/2026-03-23-parallel-fanout-web-crawl-design.md`
- `backend/app/tools/web_crawl.py`
- `backend/app/tools/schemas/web_crawl.py`
- `backend/agent/runtime_sources.py`

### Task 1: Lock the Final Combined Crawl Contract

**Files:**
- Modify: `backend/app/tools/schemas/web_crawl.py`
- Create: `backend/app/tools/schemas/web_crawl_batch.py`
- Modify: `backend/app/contracts/web_crawl.py`
- Modify: `backend/app/tools/schemas/__init__.py`
- Modify: `backend/app/contracts/__init__.py`
- Test: `backend/tests/tools/test_web_crawl_tool.py`

- [ ] **Step 1: Write the failing schema tests for the merged contract**

```python
def test_web_crawl_input_accepts_single_url_and_objective() -> None:
    model = WebCrawlInput(url="https://example.com/article", objective="Find pricing")
    assert str(model.url) == "https://example.com/article"
    assert model.objective == "Find pricing"


def test_web_crawl_batch_input_accepts_urls_and_rejects_url_plus_urls() -> None:
    with pytest.raises(ValidationError):
        WebCrawlBatchInput(url="https://example.com/a", urls=["https://example.com/b"])


def test_web_crawl_batch_success_preserves_input_order() -> None:
    payload = WebCrawlBatchSuccess.model_validate(
        {
            "requested_urls": ["https://example.com/a", "https://example.com/b"],
            "items": [
                {"url": "https://example.com/a", "status": "succeeded", "result": {...}, "error": None},
                {"url": "https://example.com/b", "status": "failed", "result": None, "error": {...}},
            ],
            "meta": {...},
            "summary": {"attempted": 2, "succeeded": 1, "failed": 1},
        }
    )
    assert [str(item.url) for item in payload.items] == [
        "https://example.com/a",
        "https://example.com/b",
    ]
```

- [ ] **Step 2: Run the schema-focused test target and confirm it fails for missing models**

Run: `pytest backend/tests/tools/test_web_crawl_tool.py -k "batch_input or preserves_input_order or single_url_and_objective" -v`
Expected: FAIL with missing batch models or validation behavior.

- [ ] **Step 3: Implement the merged public crawl schemas**

```python
class WebCrawlToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    url: HttpUrl | None = None
    urls: list[HttpUrl] | None = Field(default=None, min_length=1, max_length=5)
    objective: str | None = Field(default=None, min_length=1)


class WebCrawlBatchInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    urls: list[HttpUrl] = Field(min_length=1, max_length=5)
    objective: str | None = Field(default=None, min_length=1)


class WebCrawlBatchSummary(BaseModel):
    attempted: int = Field(ge=0)
    succeeded: int = Field(ge=0)
    failed: int = Field(ge=0)


class WebCrawlBatchItemResult(BaseModel):
    url: HttpUrl
    status: Literal["succeeded", "failed"]
    result: WebCrawlSuccess | None = None
    error: ToolError | None = None


class WebCrawlBatchSuccess(BaseModel):
    requested_urls: list[HttpUrl]
    items: list[WebCrawlBatchItemResult]
    meta: ToolMeta
    summary: WebCrawlBatchSummary
```

Run: make `WebCrawlToolInput` the single public args schema for the LangChain `web_crawl` entrypoint so the tool accepts either `url` or `urls` through one explicit contract.
Expected: one public input model, one public tool name, and no ambiguity about how batch calls enter the tool.

- [ ] **Step 4: Update the compatibility exports**

Run: update `backend/app/contracts/web_crawl.py`, `backend/app/tools/schemas/__init__.py`, and `backend/app/contracts/__init__.py` so the new batch models are importable through the existing contract layer.
Expected: imports stay explicit and callers do not need to reach into private modules.

- [ ] **Step 5: Run the schema tests again**

Run: `pytest backend/tests/tools/test_web_crawl_tool.py -k "batch_input or preserves_input_order or single_url_and_objective" -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/tools/schemas/web_crawl.py \
  backend/app/tools/schemas/web_crawl_batch.py \
  backend/app/contracts/web_crawl.py \
  backend/app/tools/schemas/__init__.py \
  backend/app/contracts/__init__.py \
  backend/tests/tools/test_web_crawl_tool.py
git commit -m "feat: add combined web crawl batch schemas"
```

### Task 2: Build the Session-Aware Single-Page Orchestrator

**Files:**
- Create: `backend/app/crawler/schemas/session_profile.py`
- Create: `backend/app/crawler/schemas/browser_fetch.py`
- Create: `backend/app/crawler/schemas/fetch_strategy.py`
- Create: `backend/app/crawler/session_profiles.py`
- Create: `backend/app/crawler/fetch_strategy.py`
- Create: `backend/app/crawler/fetch_classification.py`
- Create: `backend/app/crawler/content_normalizer.py`
- Create: `backend/app/crawler/error_mapping.py`
- Create: `backend/app/crawler/fetch_orchestrator.py`
- Create: `backend/app/crawler/browser_worker.py`
- Modify: `backend/app/tools/web_crawl.py`
- Test: `backend/tests/crawler/test_fetch_orchestrator.py`
- Test: `backend/tests/crawler/test_session_profiles.py`
- Test: `backend/tests/crawler/test_browser_worker.py`

- [ ] **Step 1: Write failing tests for session-profile resolution and HTTP-to-browser escalation**

```python
def test_resolve_session_profile_matches_domain() -> None:
    profile = resolve_session_profile("https://app.example.com/settings", profiles=[...])
    assert profile.profile_id == "example-session"


def test_orchestrator_escalates_to_browser_for_403() -> None:
    result = run_fetch_orchestrator(url="https://example.com/blocked", objective="Find pricing", ...)
    assert result.meta.strategy_used == "browser"
    assert result.meta.escalation_count == 1


def test_browser_worker_applies_seeded_session_state() -> None:
    result = browser_fetch(
        url="https://example.com/dashboard",
        seed=BrowserContextSeed(
            cookies=[...],
            headers={"x-test-header": "1"},
            local_storage=[...],
            session_storage=[...],
        ),
    )
    assert result.seed_applied.cookies is True
    assert result.seed_applied.local_storage is True
    assert result.seed_applied.session_storage is True
```

- [ ] **Step 2: Run the new crawler tests and confirm they fail**

Run: `pytest backend/tests/crawler/test_session_profiles.py backend/tests/crawler/test_fetch_orchestrator.py backend/tests/crawler/test_browser_worker.py -v`
Expected: FAIL because the new modules do not exist yet.

- [ ] **Step 3: Implement the small crawler modules**

```python
def resolve_session_profile(url: str, profiles: Sequence[SessionProfile]) -> SessionProfile | None:
    hostname = urlsplit(url).hostname or ""
    return next((profile for profile in profiles if profile.matches(hostname)), None)


def decide_fetch_strategy(... ) -> FetchStrategyDecision:
    if matched_profile and matched_profile.browser_only:
        return FetchStrategyDecision(initial_mode="browser", escalate=False)
    return FetchStrategyDecision(initial_mode="http", escalate=True)
```

- [ ] **Step 4: Route single-page `run_web_crawl(...)` through the orchestrator**

Run: keep the public `run_web_crawl(...)` entrypoint explicit, but delegate the internal single-page work to `fetch_orchestrator.py`.
Expected: no behavior regression for existing single-URL tests.

- [ ] **Step 5: Run targeted crawler and single-page crawl tests**

Run: `pytest backend/tests/crawler/test_session_profiles.py backend/tests/crawler/test_fetch_orchestrator.py backend/tests/crawler/test_browser_worker.py backend/tests/tools/test_web_crawl_tool.py -k "objective or redirect or unsupported_content_type or low_content_quality" -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/crawler \
  backend/app/tools/web_crawl.py \
  backend/tests/crawler/test_session_profiles.py \
  backend/tests/crawler/test_fetch_orchestrator.py \
  backend/tests/crawler/test_browser_worker.py \
  backend/tests/tools/test_web_crawl_tool.py
git commit -m "feat: add session-aware single-page crawl orchestration"
```

### Task 3: Add Deterministic Parallel Batch Crawl Execution

**Files:**
- Create: `backend/app/tools/web_crawl_batch.py`
- Modify: `backend/app/tools/web_crawl.py`
- Test: `backend/tests/tools/test_web_crawl_tool.py`

- [ ] **Step 1: Write failing batch execution tests**

```python
def test_web_crawl_batch_returns_ordered_mixed_results(monkeypatch) -> None:
    payload = web_crawl.invoke({"urls": ["https://example.com/a", "https://example.com/b"]})
    result = WebCrawlBatchSuccess.model_validate(payload)
    assert result.summary.attempted == 2
    assert [item.status for item in result.items] == ["succeeded", "failed"]


def test_web_crawl_batch_preserves_fallback_success_for_pdf(monkeypatch) -> None:
    payload = web_crawl.invoke({"urls": ["https://example.com/file.pdf"]})
    result = WebCrawlBatchSuccess.model_validate(payload)
    assert result.items[0].result.fallback_reason == "unsupported-content-type"


def test_web_crawl_batch_returns_per_item_invalid_request_for_policy_blocked_url(monkeypatch) -> None:
    tool = build_web_crawl_tool(
        retrieval_policy=AgentRunRetrievalPolicy.model_validate(
            {"search": {"include_domains": ["example.com"]}}
        )
    )
    payload = tool.invoke({"urls": ["https://example.com/a", "https://blocked.com/b"]})
    result = WebCrawlBatchSuccess.model_validate(payload)
    assert result.items[1].status == "failed"
    assert result.items[1].error.kind == "invalid_request"
```

- [ ] **Step 2: Run the batch execution tests and confirm they fail**

Run: `pytest backend/tests/tools/test_web_crawl_tool.py -k "batch_returns_ordered_mixed_results or batch_preserves_fallback_success_for_pdf" -v`
Expected: FAIL because the tool only handles single URLs.

- [ ] **Step 3: Implement explicit batch orchestration with bounded concurrency**

```python
def _await_batch_futures(
    requested_urls: list[str],
    futures: dict[Future[WebCrawlToolResult], str],
) -> list[WebCrawlBatchItemResult]:
    results_by_url: dict[str, WebCrawlBatchItemResult] = {}
    for future, url in futures.items():
        try:
            payload = future.result(timeout=PER_URL_TIMEOUT_SECONDS)
        except TimeoutError:
            future.cancel()
            results_by_url[url] = build_timeout_item(url)
            continue
        results_by_url[url] = build_batch_item(url=url, payload=payload)
    return [results_by_url[url] for url in requested_urls]


def run_web_crawl_batch(*, urls: list[str], objective: str | None, ...) -> WebCrawlBatchSuccess:
    with ThreadPoolExecutor(max_workers=min(len(urls), 5)) as pool:
        futures = {
            pool.submit(_crawl_one_url, url, objective=objective, ...): url
            for url in urls
        }
        ordered_results = _await_batch_futures(urls, futures)
    return build_batch_success(urls=urls, items=ordered_results, ...)
```

Run: implement explicit per-item timeout handling and cancellation instead of plain `executor.map(...)`.
Expected: one slow or hung fetch does not stall the rest of the batch, and timed-out URLs become deterministic per-item failures.

- [ ] **Step 4: Dispatch from the public tool boundary**

Run: update `build_web_crawl_tool(...)` and `run_web_crawl(...)` wiring so single-page calls keep working and `urls=[...]` takes the new batch path.
Expected: one explicit tool boundary, not a second public crawl tool.

- [ ] **Step 5: Run the full crawl tool suite**

Run: `pytest backend/tests/tools/test_web_crawl_tool.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/tools/web_crawl.py \
  backend/app/tools/web_crawl_batch.py \
  backend/tests/tools/test_web_crawl_tool.py
git commit -m "feat: add deterministic batch web crawl fan-out"
```

### Task 4: Wire Batch Results into Sources, Traces, and Runtime Output

**Files:**
- Modify: `backend/agent/runtime_sources.py`
- Modify: `backend/app/tools/web_crawl.py`
- Test: `backend/tests/agent/test_runtime.py`
- Test: `backend/tests/tools/test_web_crawl_tool.py`

- [ ] **Step 1: Write failing runtime source tests for batch crawl payloads**

```python
def test_extract_sources_flattens_successful_batch_crawl_items() -> None:
    registry = extract_sources(
        {
            "messages": [
                {"type": "tool", "name": "web_crawl", "payload": batch_payload_with_one_success_one_failure()}
            ]
        }
    )
    assert [str(source.url) for source in registry.sources()] == ["https://example.com/a"]
```

- [ ] **Step 2: Run the targeted runtime tests and confirm failure**

Run: `pytest backend/tests/agent/test_runtime.py -k "batch_crawl" -v`
Expected: FAIL because batch payloads are ignored by `runtime_sources`.

- [ ] **Step 3: Implement batch-source flattening and action-record support**

```python
try:
    batch_result = WebCrawlBatchSuccess.model_validate(payload)
except ValidationError:
    batch_result = None

if batch_result is not None:
    for item in batch_result.items:
        if item.result is not None:
            register_crawl_success(registry, item.result)
    return
```

- [ ] **Step 4: Ensure all-failed valid batches remain observable**

Run: make sure logs/traces still show attempted URLs and failures even when `summary.succeeded == 0`.
Expected: no silent drop of batch attempts from runtime traces.

- [ ] **Step 5: Run runtime and tool tests**

Run: `pytest backend/tests/agent/test_runtime.py backend/tests/tools/test_web_crawl_tool.py -k "batch_crawl or action_record" -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/agent/runtime_sources.py \
  backend/app/tools/web_crawl.py \
  backend/tests/agent/test_runtime.py \
  backend/tests/tools/test_web_crawl_tool.py
git commit -m "feat: surface batch crawl results in runtime sources"
```

### Task 5: Update Prompt Guidance for Search-Then-Batch-Open Behavior

**Files:**
- Modify: `backend/agent/prompts.py`
- Test: `backend/tests/agent/test_runtime.py`

- [ ] **Step 1: Write a failing prompt-building test**

```python
def test_system_prompt_instructs_agent_to_batch_selected_url_opens() -> None:
    prompt = build_system_prompt(profile=RUNTIME_PROFILES["agentic"])
    assert "call web_crawl with multiple selected URLs in one call" in prompt
```

- [ ] **Step 2: Run the prompt test and confirm it fails**

Run: `pytest backend/tests/agent/test_runtime.py -k "batch_selected_url_opens" -v`
Expected: FAIL because the prompt only talks about one-page crawl selection today.

- [ ] **Step 3: Update the base system prompt and any profile guidance needed**

```python
BASE_SYSTEM_PROMPT = """
...
Use web_search to shortlist likely-answering sources before crawling.
When several search results look promising, call web_crawl with multiple selected URLs in one call.
Use one-by-one crawling only when you need to branch after reading an earlier page.
"""
```

- [ ] **Step 4: Run the prompt/runtime tests again**

Run: `pytest backend/tests/agent/test_runtime.py -k "batch_selected_url_opens" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/agent/prompts.py backend/tests/agent/test_runtime.py
git commit -m "feat: guide agent toward batch page opens"
```

### Task 6: Final Regression Pass and Compatibility Verification

**Files:**
- Modify: any touched files from earlier tasks as needed
- Test: `backend/tests/tools/test_web_search_tool.py`
- Test: `backend/tests/tools/test_web_crawl_tool.py`
- Test: `backend/tests/agent/test_runtime.py`
- Test: `backend/tests/crawler/`

- [ ] **Step 1: Run the core targeted suites**

Run: `pytest backend/tests/tools/test_web_search_tool.py backend/tests/tools/test_web_crawl_tool.py backend/tests/agent/test_runtime.py backend/tests/crawler -v`
Expected: PASS

- [ ] **Step 2: Run focused API coverage if crawl contracts are exposed through the agent route**

Run: `pytest backend/tests/api/test_agent_run_route.py -k "crawl or search" -v`
Expected: PASS

- [ ] **Step 3: Verify import compatibility explicitly**

Run: `python - <<'PY'\nfrom backend.app.contracts.web_crawl import WebCrawlToolResult\nprint(WebCrawlToolResult)\nPY`
Expected: prints the updated crawl contract type without import errors.

- [ ] **Step 4: Review git diff for contract drift or oversized files**

Run: `git diff --stat HEAD~6..HEAD`
Expected: the changes stay concentrated in focused modules rather than a monolithic `web_crawl.py`.

- [ ] **Step 5: Commit final fixups**

```bash
git add backend docs
git commit -m "test: verify combined session-aware batch crawl flow"
```

## Notes for the Implementer

- Keep runtime paths explicit. Do not hide batch orchestration or strategy decisions behind generic callable registries.
- Preserve backward compatibility for existing single-URL callers while converging on one final public `web_crawl` contract.
- Treat invalid request-shape failures differently from per-item policy failures exactly as the approved spec states.
- Reuse existing `WebCrawlSuccess` semantics for fallback successes inside batch items.
- Keep new files small and responsibility-focused. If `backend/app/tools/web_crawl.py` starts growing into orchestration logic, move that logic into dedicated modules immediately.
