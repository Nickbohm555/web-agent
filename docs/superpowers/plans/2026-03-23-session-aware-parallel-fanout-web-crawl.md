# Session-Aware Parallel Fan-Out Web Crawl Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade `open_url` into one final session-aware crawl tool that supports deterministic parallel fan-out for a selected batch of URLs while preserving typed results, source extraction, and backward compatibility for single-page calls.

**Architecture:** Keep one agent-facing `open_url` boundary and merge the approved session-aware and parallel fan-out designs into a single contract. Add focused batch schemas and orchestration modules, preserve the existing single-page extractor/fallback behavior, and extend runtime source handling so successful batch items become citations the same way single-page crawl successes do today.

**Tech Stack:** Python, Pydantic, LangChain/LangGraph tool entrypoints, httpx, Playwright-backed crawler modules, pytest

---

## File Structure

**Create:**
- `backend/app/tools/schemas/open_url_batch.py` - Batch input and ordered batch result models for `open_url`.
- `backend/app/tools/open_url_batch.py` - Deterministic parallel batch orchestration and result aggregation.
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
- `backend/app/tools/schemas/open_url.py` - Merge the final single/batch/session-aware public tool schemas.
- `backend/app/contracts/open_url.py` - Re-export the updated crawl contract types.
- `backend/app/tools/schemas/__init__.py` - Export new batch crawl schemas.
- `backend/app/contracts/__init__.py` - Export updated crawl contract types if needed.
- `backend/app/tools/open_url.py` - Single-vs-batch dispatch, final tool docstring, policy checks, and entrypoint wiring.
- `backend/app/tools/__init__.py` - Export updated crawl tool symbols if needed.
- `backend/agent/runtime_sources.py` - Flatten successful batch crawl items into runtime sources/citations.
- `backend/agent/prompts.py` - Instruct the agent to batch selected URL opens with `open_url`.
- `backend/tests/tools/test_open_url_tool.py` - Expand tool tests for final combined single/batch behavior.
- `backend/tests/agent/test_runtime.py` - Add runtime/source-registry coverage for batch crawl results.
- `backend/tests/crawler/test_http_worker.py` - Adjust only if shared fetch models change.
- `backend/tests/crawler/` new or existing test modules - Add session-profile, strategy, browser, and orchestrator tests.

**Reference While Implementing:**
- `docs/superpowers/specs/2026-03-23-session-aware-web-crawl-design.md`
- `docs/superpowers/specs/2026-03-23-parallel-fanout-web-crawl-design.md`
- `backend/app/tools/open_url.py`
- `backend/app/tools/schemas/open_url.py`
- `backend/agent/runtime_sources.py`

### Task 1: Lock the Final Combined Crawl Contract

**Files:**
- Modify: `backend/app/tools/schemas/open_url.py`
- Create: `backend/app/tools/schemas/open_url_batch.py`
- Modify: `backend/app/contracts/open_url.py`
- Modify: `backend/app/tools/schemas/__init__.py`
- Modify: `backend/app/contracts/__init__.py`
- Test: `backend/tests/tools/test_open_url_tool.py`

- [ ] **Step 1: Write the failing schema tests for the merged contract**

```python
def test_open_url_input_accepts_single_url_and_objective() -> None:
    model = OpenUrlToolInput(url="https://example.com/article", objective="Find pricing")
    assert str(model.url) == "https://example.com/article"
    assert model.objective == "Find pricing"


def test_open_url_tool_input_accepts_urls_and_rejects_url_plus_urls() -> None:
    with pytest.raises(ValidationError):
        OpenUrlToolInput(url="https://example.com/a", urls=["https://example.com/b"])


def test_open_url_tool_input_rejects_missing_url_and_urls() -> None:
    with pytest.raises(ValidationError):
        OpenUrlToolInput()


def test_open_url_tool_input_rejects_more_than_five_urls() -> None:
    with pytest.raises(ValidationError):
        OpenUrlToolInput(urls=[f"https://example.com/{index}" for index in range(6)])


def test_open_url_batch_success_preserves_input_order() -> None:
    payload = OpenUrlBatchSuccess.model_validate(
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

Run: `pytest backend/tests/tools/test_open_url_tool.py -k "tool_input or preserves_input_order or single_url_and_objective" -v`
Expected: FAIL with missing batch models or validation behavior.

- [ ] **Step 3: Implement the merged public crawl schemas**

```python
class OpenUrlToolInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    url: HttpUrl | None = None
    urls: list[HttpUrl] | None = Field(default=None, min_length=1, max_length=5)
    objective: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_target_shape(self) -> "OpenUrlToolInput":
        if (self.url is None) == (self.urls is None):
            raise ValueError("exactly one of url or urls must be provided")
        return self


class OpenUrlBatchInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    urls: list[HttpUrl] = Field(min_length=1, max_length=5)
    objective: str | None = Field(default=None, min_length=1)


class OpenUrlBatchSummary(BaseModel):
    attempted: int = Field(ge=0)
    succeeded: int = Field(ge=0)
    failed: int = Field(ge=0)


class OpenUrlBatchItemResult(BaseModel):
    url: HttpUrl
    status: Literal["succeeded", "failed"]
    result: OpenUrlSuccess | None = None
    error: ToolError | None = None


class OpenUrlBatchSuccess(BaseModel):
    requested_urls: list[HttpUrl]
    items: list[OpenUrlBatchItemResult]
    meta: ToolMeta
    summary: OpenUrlBatchSummary
```

Run: make `OpenUrlToolInput` the single public args schema for the LangChain `open_url` entrypoint so the tool accepts either `url` or `urls` through one explicit contract.
Expected: one public input model, one public tool name, and no ambiguity about how batch calls enter the tool.

- [ ] **Step 4: Extend crawl metadata typing for session-aware fields**

```python
class OpenUrlMeta(ToolMeta):
    strategy_used: Literal["http", "browser"]
    escalation_count: int = Field(ge=0)
    session_profile_id: str | None = None
    block_reason: str | None = None
    rendered: bool = False
    challenge_detected: bool = False
```

Run: update the typed crawl success contract so the session-aware metadata promised by the spec exists before orchestrator work starts.
Expected: `OpenUrlSuccess.meta` and any batch item success path can surface session-aware metadata without ad hoc dict fields.

- [ ] **Step 5: Update the compatibility exports**

Run: update `backend/app/contracts/open_url.py`, `backend/app/tools/schemas/__init__.py`, and `backend/app/contracts/__init__.py` so the new batch models are importable through the existing contract layer.
Expected: imports stay explicit and callers do not need to reach into private modules.

- [ ] **Step 6: Run the schema tests again**

Run: `pytest backend/tests/tools/test_open_url_tool.py -k "tool_input or preserves_input_order or single_url_and_objective" -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/tools/schemas/open_url.py \
  backend/app/tools/schemas/open_url_batch.py \
  backend/app/contracts/open_url.py \
  backend/app/tools/schemas/__init__.py \
  backend/app/contracts/__init__.py \
  backend/tests/tools/test_open_url_tool.py
git commit -m "feat: add combined open_url batch schemas"
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
- Modify: `backend/app/tools/open_url.py`
- Test: `backend/tests/crawler/test_fetch_orchestrator.py`
- Test: `backend/tests/crawler/test_session_profiles.py`
- Test: `backend/tests/crawler/test_browser_worker.py`

- [ ] **Step 1: Write failing tests for session-profile resolution and HTTP-to-browser escalation**

```python
def test_resolve_session_profile_matches_domain() -> None:
    profile = resolve_session_profile("https://app.example.com/settings", profiles=[...])
    assert profile.profile_id == "example-session"


def test_get_session_profiles_returns_configured_profiles() -> None:
    provider = InMemorySessionProfileProvider(profiles=[SessionProfile(profile_id="example-session", ...)])
    profiles = get_session_profiles(provider)
    assert profiles[0].profile_id == "example-session"


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
class SessionProfileProvider(Protocol):
    def list_profiles(self) -> Sequence[SessionProfile]:
        ...


class InMemorySessionProfileProvider:
    def __init__(self, profiles: Sequence[SessionProfile]) -> None:
        self._profiles = list(profiles)

    def list_profiles(self) -> Sequence[SessionProfile]:
        return tuple(self._profiles)


def get_session_profiles(provider: SessionProfileProvider | None) -> Sequence[SessionProfile]:
    return provider.list_profiles() if provider is not None else ()


def resolve_session_profile(url: str, profiles: Sequence[SessionProfile]) -> SessionProfile | None:
    hostname = urlsplit(url).hostname or ""
    return next((profile for profile in profiles if profile.matches(hostname)), None)


def decide_fetch_strategy(... ) -> FetchStrategyDecision:
    if matched_profile and matched_profile.browser_only:
        return FetchStrategyDecision(initial_mode="browser", escalate=False)
    return FetchStrategyDecision(initial_mode="http", escalate=True)
```

- [ ] **Step 4: Route single-page `run_open_url(...)` through the orchestrator**

```python
def run_open_url(
    *,
    url: str | None = None,
    urls: list[str] | None = None,
    objective: str | None = None,
    session_profile_provider: SessionProfileProvider | None = None,
    ...
) -> OpenUrlToolResult:
    validated = OpenUrlToolInput(url=url, urls=urls, objective=objective)
    if validated.urls is not None:
        return run_open_url_batch(
            urls=[str(item) for item in validated.urls],
            objective=validated.objective,
            session_profile_provider=session_profile_provider,
            ...,
        )
    return run_single_open_url(
        url=str(validated.url),
        objective=validated.objective,
        session_profile_provider=session_profile_provider,
        ...,
    )
```

Run: keep the public `run_open_url(...)` entrypoint explicit, validate through `OpenUrlToolInput`, and pass the provider seam into the orchestrator/browser path.
Expected: no behavior regression for existing single-URL tests and no ambiguity at the tool boundary.

- [ ] **Step 5: Run targeted crawler and single-page crawl tests**

Run: `pytest backend/tests/crawler/test_session_profiles.py backend/tests/crawler/test_fetch_orchestrator.py backend/tests/crawler/test_browser_worker.py backend/tests/tools/test_open_url_tool.py -k "objective or redirect or unsupported_content_type or low_content_quality" -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/crawler \
  backend/app/tools/open_url.py \
  backend/tests/crawler/test_session_profiles.py \
  backend/tests/crawler/test_fetch_orchestrator.py \
  backend/tests/crawler/test_browser_worker.py \
  backend/tests/tools/test_open_url_tool.py
git commit -m "feat: add session-aware single-page crawl orchestration"
```

### Task 3: Add Deterministic Parallel Batch Crawl Execution

**Files:**
- Create: `backend/app/tools/open_url_batch.py`
- Modify: `backend/app/tools/open_url.py`
- Test: `backend/tests/tools/test_open_url_tool.py`

- [ ] **Step 1: Write failing batch execution tests**

```python
def test_open_url_batch_returns_ordered_mixed_results(monkeypatch) -> None:
    payload = open_url.invoke({"urls": ["https://example.com/a", "https://example.com/b"]})
    result = OpenUrlBatchSuccess.model_validate(payload)
    assert result.summary.attempted == 2
    assert [item.status for item in result.items] == ["succeeded", "failed"]


def test_open_url_batch_preserves_fallback_success_for_pdf(monkeypatch) -> None:
    payload = open_url.invoke({"urls": ["https://example.com/file.pdf"]})
    result = OpenUrlBatchSuccess.model_validate(payload)
    assert result.items[0].result.fallback_reason == "unsupported-content-type"


def test_open_url_batch_returns_per_item_invalid_request_for_policy_blocked_url(monkeypatch) -> None:
    tool = build_open_url_tool(
        retrieval_policy=AgentRunRetrievalPolicy.model_validate(
            {"search": {"include_domains": ["example.com"]}}
        )
    )
    payload = tool.invoke({"urls": ["https://example.com/a", "https://blocked.com/b"]})
    result = OpenUrlBatchSuccess.model_validate(payload)
    assert result.items[1].status == "failed"
    assert result.items[1].error.kind == "invalid_request"
```

- [ ] **Step 2: Run the batch execution tests and confirm they fail**

Run: `pytest backend/tests/tools/test_open_url_tool.py -k "batch_returns_ordered_mixed_results or batch_preserves_fallback_success_for_pdf" -v`
Expected: FAIL because the tool only handles single URLs.

- [ ] **Step 3: Implement explicit batch orchestration with bounded concurrency**

```python
def _await_batch_futures(
    requested_urls: list[str],
    futures: dict[Future[OpenUrlToolResult], str],
) -> list[OpenUrlBatchItemResult]:
    results_by_url: dict[str, OpenUrlBatchItemResult] = {}
    pending = set(futures)
    while pending:
        done, pending = wait(
            pending,
            timeout=PER_URL_TIMEOUT_SECONDS,
            return_when=FIRST_COMPLETED,
        )
        if not done:
            for future in pending:
                future.cancel()
                url = futures[future]
                results_by_url[url] = build_timeout_item(url)
            break
        for future in done:
            url = futures[future]
            try:
                payload = future.result()
            except TimeoutError:
                future.cancel()
                results_by_url[url] = build_timeout_item(url)
                continue
            except Exception as exc:
                results_by_url[url] = build_exception_item(url, exc)
                continue
            results_by_url[url] = build_batch_item(url=url, payload=payload)
    return [results_by_url[url] for url in requested_urls]


def run_open_url_batch(*, urls: list[str], objective: str | None, ...) -> OpenUrlBatchSuccess:
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

```python
@tool("open_url", args_schema=OpenUrlToolInput)
def bounded_open_url(
    url: str | None = None,
    urls: list[str] | None = None,
    objective: str | None = None,
) -> OpenUrlToolResult:
    return run_open_url(
        url=url,
        urls=urls,
        objective=objective,
        session_profile_provider=session_profile_provider,
        ...,
    )
```

Run: update `build_open_url_tool(...)` so the LangChain wrapper signature matches the validated one-of input contract exactly and routes both single and batch requests through `run_open_url(...)`.
Expected: one explicit tool boundary, not a second public crawl tool.

- [ ] **Step 5: Run the full crawl tool suite**

Run: `pytest backend/tests/tools/test_open_url_tool.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/tools/open_url.py \
  backend/app/tools/open_url_batch.py \
  backend/tests/tools/test_open_url_tool.py
git commit -m "feat: add deterministic batch open_url fan-out"
```

### Task 4: Wire Batch Results into Sources, Traces, and Runtime Output

**Files:**
- Modify: `backend/agent/runtime_sources.py`
- Modify: `backend/app/tools/open_url.py`
- Test: `backend/tests/agent/test_runtime.py`
- Test: `backend/tests/tools/test_open_url_tool.py`

- [ ] **Step 1: Write failing runtime source tests for batch crawl payloads**

```python
def test_extract_sources_flattens_successful_batch_crawl_items() -> None:
    registry = extract_sources(
        {
            "messages": [
                {"type": "tool", "name": "open_url", "payload": batch_payload_with_one_success_one_failure()}
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
    batch_result = OpenUrlBatchSuccess.model_validate(payload)
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

Run: `pytest backend/tests/agent/test_runtime.py backend/tests/tools/test_open_url_tool.py -k "batch_crawl or action_record" -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/agent/runtime_sources.py \
  backend/app/tools/open_url.py \
  backend/tests/agent/test_runtime.py \
  backend/tests/tools/test_open_url_tool.py
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
    assert "call open_url with multiple selected URLs in one call" in prompt
```

- [ ] **Step 2: Run the prompt test and confirm it fails**

Run: `pytest backend/tests/agent/test_runtime.py -k "batch_selected_url_opens" -v`
Expected: FAIL because the prompt only talks about one-page crawl selection today.

- [ ] **Step 3: Update the base system prompt and any profile guidance needed**

```python
BASE_SYSTEM_PROMPT = """
...
Use web_search to shortlist likely-answering sources before crawling.
When several search results look promising, call open_url with multiple selected URLs in one call.
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
- Test: `backend/tests/tools/test_open_url_tool.py`
- Test: `backend/tests/agent/test_runtime.py`
- Test: `backend/tests/crawler/`

- [ ] **Step 1: Run the core targeted suites**

Run: `pytest backend/tests/tools/test_web_search_tool.py backend/tests/tools/test_open_url_tool.py backend/tests/agent/test_runtime.py backend/tests/crawler -v`
Expected: PASS

- [ ] **Step 2: Run focused API coverage if crawl contracts are exposed through the agent route**

Run: `pytest backend/tests/api/test_agent_run_route.py -k "crawl or search" -v`
Expected: PASS

- [ ] **Step 3: Verify import compatibility explicitly**

Run: `python - <<'PY'\nfrom backend.app.contracts.open_url import OpenUrlToolResult\nprint(OpenUrlToolResult)\nPY`
Expected: prints the updated crawl contract type without import errors.

- [ ] **Step 4: Review git diff for contract drift or oversized files**

Run: `git diff --stat HEAD~6..HEAD`
Expected: the changes stay concentrated in focused modules rather than a monolithic `open_url.py`.

- [ ] **Step 5: Commit final fixups**

```bash
git add backend docs
git commit -m "test: verify combined session-aware batch crawl flow"
```

## Notes for the Implementer

- Keep runtime paths explicit. Do not hide batch orchestration or strategy decisions behind generic callable registries.
- Preserve backward compatibility for existing single-URL callers while converging on one final public `open_url` contract.
- Treat invalid request-shape failures differently from per-item policy failures exactly as the approved spec states.
- Reuse existing `OpenUrlSuccess` semantics for fallback successes inside batch items.
- Keep new files small and responsibility-focused. If `backend/app/tools/open_url.py` starts growing into orchestration logic, move that logic into dedicated modules immediately.
