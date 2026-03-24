# Session-Aware Web Crawl Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade `open_url(url, objective)` into a session-aware, multi-strategy crawl pipeline that can escalate from HTTP to browser-backed retrieval, seed stored session state by domain, and return typed success only when real evidence is recovered.

**Architecture:** Keep `open_url` as the only agent-facing crawl surface, but move fetch decision-making into deterministic crawler modules. Resolve a matched session profile first, run HTTP when allowed, classify the result, escalate to a Playwright browser worker when needed, normalize HTTP/browser content into one extraction path, and map no-evidence endings into typed failures instead of silent success. Keep modules atomic: schemas stay feature-local under `backend/app/crawler/schemas/`, orchestration stays in small focused files, and runtime/source registration only treats evidence-bearing crawl successes as sources.

**Tech Stack:** FastAPI backend, Pydantic v2 schemas, `httpx`, Playwright Python, `trafilatura`, LangChain tool wrappers, `pytest`, Docker Compose

---

## File Structure

### New Files

- `backend/app/crawler/session_profiles.py`
  - Load configured session profiles and resolve the best domain match for a URL.
- `backend/app/crawler/fetch_strategy.py`
  - Decide initial fetch mode and whether a classification should escalate to browser.
- `backend/app/crawler/fetch_classification.py`
  - Convert HTTP/browser outcomes and extraction quality into stable typed classifications.
- `backend/app/crawler/fetch_orchestrator.py`
  - Coordinate session resolution, strategy selection, HTTP/browser execution, normalization, extraction, and error mapping.
- `backend/app/crawler/browser_worker.py`
  - Run Playwright navigation with deterministic context seeding from a matched session profile.
- `backend/app/crawler/content_normalizer.py`
  - Normalize HTTP and browser payloads into one extraction-ready content model.
- `backend/app/crawler/error_mapping.py`
  - Map internal crawl failures/classifications into typed `OpenUrlError` payloads.
- `backend/app/crawler/schemas/session_profile.py`
  - `SessionProfile`, `SessionCookie`, `SessionHeader`, `StorageSeedEntry`, `DomainSessionMatch`.
- `backend/app/crawler/schemas/browser_fetch.py`
  - `BrowserContextSeed`, `BrowserFetchSuccess`, `BrowserFetchFailure`.
- `backend/app/crawler/schemas/fetch_strategy.py`
  - `FetchStrategyDecision`, `FetchEscalationReason`, `FetchClassification`.
- `backend/tests/crawler/test_session_profiles.py`
  - Resolver coverage for domain matching and forced-browser profiles.
- `backend/tests/crawler/test_fetch_strategy.py`
  - Deterministic strategy/escalation coverage.
- `backend/tests/crawler/test_browser_worker.py`
  - Browser seeding and rendered-content capture coverage with stubbed Playwright seams.
- `backend/tests/crawler/test_fetch_orchestrator.py`
  - End-to-end crawler orchestration coverage for success, escalation, and typed failures.

### Modified Files

- `backend/app/crawler/http_worker.py`
  - Keep HTTP fetching focused, but expose enough typed data for classification/orchestration and add a concise docstring on `fetch()`.
- `backend/app/crawler/extractor.py`
  - Preserve extraction responsibility while returning enough signal for escalation and no-evidence failure decisions.
- `backend/app/crawler/schemas/http_fetch.py`
  - Extend HTTP result models only if orchestration needs additional stable fields.
- `backend/app/crawler/schemas/__init__.py`
  - Export new crawler-local schemas.
- `backend/app/tools/schemas/open_url.py`
  - Extend crawl success/error metadata and remove any shape drift with new classifications.
- `backend/app/tools/schemas/__init__.py`
  - Re-export updated crawl tool schemas if needed.
- `backend/app/tools/open_url.py`
  - Replace direct `HttpFetchWorker` orchestration with the new fetch orchestrator while keeping the same tool surface and accurate tool description.
- `backend/agent/runtime_sources.py`
  - Only register crawl sources when success payloads contain evidence-bearing content.
- `backend/agent/runtime_execution.py`
  - Warn or tighten behavior around tool-backed completions with zero sources after crawl attempts.
- `backend/tests/tools/test_open_url_tool.py`
  - Update tool contract tests for strategy metadata, escalation, and typed no-evidence failures.
- `backend/tests/agent/test_runtime.py`
  - Add runtime regressions for zero-evidence completions and source registration behavior.
- `backend/requirements.txt`
  - Add Playwright Python dependency.
- `backend/Dockerfile`
  - Install browser runtime dependencies and Playwright browsers for backend container execution.
- `docker-compose.yml`
  - Only if needed for backend browser environment variables or larger shared memory; skip if current compose works unchanged.

### Existing Files To Read Before Editing

- `docs/superpowers/specs/2026-03-23-session-aware-web-crawl-design.md`
- `backend/app/tools/open_url.py`
- `backend/app/tools/schemas/open_url.py`
- `backend/app/crawler/http_worker.py`
- `backend/app/crawler/extractor.py`
- `backend/agent/runtime_sources.py`
- `backend/agent/runtime_execution.py`
- `backend/tests/tools/test_open_url_tool.py`
- `backend/tests/agent/test_runtime.py`

### Planned Cleanup / Migration

- Stop importing crawl schemas from misplaced top-level files in `backend/app/schemas/open_url.py` and `backend/app/schemas/__init__.py`.
- Remove now-redundant top-level crawl schema exports once all imports point at `backend/app/tools/schemas/open_url.py` and `backend/app/crawler/schemas/*`.
- Keep `backend/app/contracts/open_url.py` aligned or remove stale bridging only if the rest of the repo no longer needs it.

### Implementation Notes

- Use `@superpowers:test-driven-development` for each task: write one failing test, run it, implement the minimum code, rerun the focused test, then commit.
- Use `@superpowers:verification-before-completion` before claiming the full plan is finished.
- Prefer direct runtime calls over generic runner indirection. Inject only narrow seams for Playwright page/context factories, profile loaders, or HTTP/browser workers.
- Keep each crawler module single-purpose. If a planned file starts accumulating policy + orchestration + normalization together, split it before implementation.

## Task 1: Establish Session Profile Schemas And Resolver

**Files:**
- Create: `backend/app/crawler/schemas/session_profile.py`
- Create: `backend/app/crawler/session_profiles.py`
- Modify: `backend/app/crawler/schemas/__init__.py`
- Test: `backend/tests/crawler/test_session_profiles.py`

- [ ] **Step 1: Write the failing resolver tests**

```python
from backend.app.crawler.session_profiles import resolve_session_profile
from backend.app.crawler.schemas.session_profile import SessionProfile


def test_resolve_session_profile_prefers_exact_domain_match() -> None:
    profiles = [
        SessionProfile(profile_id="broad", domains=["example.com"]),
        SessionProfile(profile_id="exact", domains=["app.example.com"]),
    ]

    match = resolve_session_profile("https://app.example.com/account", profiles=profiles)

    assert match is not None
    assert match.profile.profile_id == "exact"
    assert match.matched_domain == "app.example.com"


def test_resolve_session_profile_returns_none_when_domain_is_unmatched() -> None:
    profiles = [SessionProfile(profile_id="docs", domains=["docs.example.com"])]

    assert resolve_session_profile("https://www.example.com/", profiles=profiles) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/crawler/test_session_profiles.py -v`
Expected: FAIL with import errors for `session_profiles` / `session_profile`

- [ ] **Step 3: Write minimal schema and resolver implementation**

```python
class SessionProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    profile_id: str = Field(min_length=1)
    domains: list[str] = Field(min_length=1)
    browser_only: bool = False
    cookies: list[SessionCookie] = Field(default_factory=list)
    headers: list[SessionHeader] = Field(default_factory=list)
    local_storage: list[StorageSeedEntry] = Field(default_factory=list)
    session_storage: list[StorageSeedEntry] = Field(default_factory=list)
    ttl_seconds: int | None = Field(default=None, gt=0)


def resolve_session_profile(
    url: str,
    *,
    profiles: Sequence[SessionProfile],
) -> DomainSessionMatch | None:
    hostname = urlsplit(url).hostname or ""
    ranked = [
        (domain, profile)
        for profile in profiles
        for domain in profile.domains
        if hostname == domain or hostname.endswith(f".{domain}")
    ]
    if not ranked:
        return None
    matched_domain, profile = max(ranked, key=lambda item: len(item[0]))
    return DomainSessionMatch(profile=profile, matched_domain=matched_domain)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/crawler/test_session_profiles.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/crawler/schemas/session_profile.py backend/app/crawler/session_profiles.py backend/app/crawler/schemas/__init__.py backend/tests/crawler/test_session_profiles.py
git commit -m "feat: add session profile resolver"
```

## Task 2: Add Fetch Strategy And Classification Models

**Files:**
- Create: `backend/app/crawler/schemas/fetch_strategy.py`
- Create: `backend/app/crawler/fetch_classification.py`
- Modify: `backend/app/crawler/extractor.py`
- Test: `backend/tests/crawler/test_fetch_strategy.py`

- [ ] **Step 1: Write the failing strategy tests**

```python
from backend.app.crawler.fetch_strategy import decide_fetch_strategy, should_escalate_to_browser
from backend.app.crawler.schemas.fetch_strategy import FetchClassification
from backend.app.crawler.schemas.session_profile import DomainSessionMatch, SessionProfile


def test_decide_fetch_strategy_starts_with_browser_for_browser_only_profile() -> None:
    decision = decide_fetch_strategy(
        url="https://app.example.com",
        session_match=DomainSessionMatch(
            matched_domain="app.example.com",
            profile=SessionProfile(profile_id="auth", domains=["app.example.com"], browser_only=True),
        ),
    )

    assert decision.initial_mode == "browser"
    assert decision.escalation_reason is None


def test_should_escalate_to_browser_for_http_403() -> None:
    classification = FetchClassification(label="auth_required", should_escalate=True, block_reason="403")

    assert should_escalate_to_browser(classification) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/crawler/test_fetch_strategy.py -v`
Expected: FAIL with missing strategy/classification modules

- [ ] **Step 3: Write minimal strategy and classification code**

```python
def decide_fetch_strategy(
    *,
    url: str,
    session_match: DomainSessionMatch | None,
) -> FetchStrategyDecision:
    if session_match and session_match.profile.browser_only:
        return FetchStrategyDecision(initial_mode="browser", escalation_reason=None)
    return FetchStrategyDecision(initial_mode="http", escalation_reason=None)


def classify_http_result(
    *,
    status_code: int | None,
    extraction_state: str | None,
    content_type: str | None,
    body_text: str,
) -> FetchClassification:
    if status_code in {401, 403}:
        return FetchClassification(label="auth_required", should_escalate=True, block_reason=str(status_code))
    if extraction_state == "low-content-quality":
        return FetchClassification(label="low_content_quality", should_escalate=True)
    if "javascript required" in body_text.lower():
        return FetchClassification(label="js_required", should_escalate=True)
    return FetchClassification(label="ok", should_escalate=False)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/crawler/test_fetch_strategy.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/crawler/schemas/fetch_strategy.py backend/app/crawler/fetch_classification.py backend/app/crawler/fetch_strategy.py backend/app/crawler/extractor.py backend/tests/crawler/test_fetch_strategy.py
git commit -m "feat: add crawl fetch strategy classification"
```

## Task 3: Add Browser Fetch Schemas And Playwright Worker

**Files:**
- Create: `backend/app/crawler/schemas/browser_fetch.py`
- Create: `backend/app/crawler/browser_worker.py`
- Modify: `backend/requirements.txt`
- Modify: `backend/Dockerfile`
- Modify: `docker-compose.yml` (only if browser runtime needs explicit container tuning)
- Test: `backend/tests/crawler/test_browser_worker.py`

- [ ] **Step 1: Write the failing browser worker tests**

```python
from backend.app.crawler.browser_worker import BrowserFetchWorker
from backend.app.crawler.schemas.session_profile import SessionProfile, SessionCookie, SessionHeader, StorageSeedEntry


def test_browser_worker_seeds_profile_state_before_navigation(fake_playwright) -> None:
    worker = BrowserFetchWorker(playwright_factory=fake_playwright)
    profile = SessionProfile(
        profile_id="auth",
        domains=["app.example.com"],
        cookies=[SessionCookie(name="session", value="abc", domain="app.example.com")],
        headers=[SessionHeader(name="x-test", value="1")],
        local_storage=[StorageSeedEntry(key="token", value="abc")],
        session_storage=[StorageSeedEntry(key="mode", value="member")],
    )

    result = worker.fetch(url="https://app.example.com/home", session_profile=profile)

    assert result.rendered is True
    assert result.session_profile_id == "auth"
    fake_playwright.assert_storage_seeded("token", "abc")


def test_browser_worker_returns_typed_navigation_failure(fake_playwright) -> None:
    fake_playwright.fail_navigation("timeout")
    worker = BrowserFetchWorker(playwright_factory=fake_playwright)

    result = worker.fetch(url="https://app.example.com/home", session_profile=None)

    assert result.error.kind == "browser_navigation_failed"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/crawler/test_browser_worker.py -v`
Expected: FAIL with missing Playwright worker/schema modules

- [ ] **Step 3: Write minimal browser worker and dependency wiring**

```python
class BrowserFetchWorker:
    def __init__(self, *, playwright_factory: PlaywrightFactory | None = None) -> None:
        self._playwright_factory = playwright_factory or sync_playwright

    def fetch(
        self,
        *,
        url: str,
        session_profile: SessionProfile | None,
    ) -> BrowserFetchSuccess | BrowserFetchFailure:
        with self._playwright_factory() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(extra_http_headers=_headers(session_profile))
            _seed_context(context, session_profile)
            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=15_000)
            html = page.content()
            text = page.locator("body").inner_text()
            return BrowserFetchSuccess(
                url=url,
                final_url=page.url,
                status_code=200,
                html=html,
                visible_text=text,
                rendered=True,
                session_profile_id=session_profile.profile_id if session_profile else None,
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/crawler/test_browser_worker.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/crawler/schemas/browser_fetch.py backend/app/crawler/browser_worker.py backend/requirements.txt backend/Dockerfile docker-compose.yml backend/tests/crawler/test_browser_worker.py
git commit -m "feat: add playwright crawl worker"
```

## Task 4: Normalize Multi-Source Fetch Output And Error Mapping

**Files:**
- Create: `backend/app/crawler/content_normalizer.py`
- Create: `backend/app/crawler/error_mapping.py`
- Modify: `backend/app/crawler/schemas/http_fetch.py`
- Modify: `backend/app/tools/schemas/open_url.py`
- Test: `backend/tests/crawler/test_fetch_orchestrator.py`

- [ ] **Step 1: Write the failing normalization/error tests**

```python
from backend.app.crawler.content_normalizer import normalize_browser_fetch, normalize_http_fetch
from backend.app.crawler.error_mapping import map_crawl_failure


def test_normalize_browser_fetch_prefers_rendered_html_and_visible_text() -> None:
    normalized = normalize_browser_fetch(html="<html><body>Hello</body></html>", visible_text="Hello")

    assert normalized.body == "<html><body>Hello</body></html>"
    assert normalized.visible_text == "Hello"
    assert normalized.rendered is True


def test_map_crawl_failure_returns_auth_required_error() -> None:
    error = map_crawl_failure(kind="auth_required", message="profile required", status_code=403)

    assert error.error.kind == "auth_required"
    assert error.error.status_code == 403
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/crawler/test_fetch_orchestrator.py -k "normalize or map_crawl_failure" -v`
Expected: FAIL with missing normalizer/error mapping functions

- [ ] **Step 3: Write minimal normalization and typed error code**

```python
def normalize_http_fetch(fetch: HttpFetchSuccess) -> NormalizedCrawlContent:
    return NormalizedCrawlContent(
        body=fetch.body,
        visible_text=fetch.body,
        content_type=fetch.content_type,
        final_url=fetch.final_url,
        status_code=fetch.status_code,
        rendered=False,
    )


def normalize_browser_fetch(*, html: str, visible_text: str) -> NormalizedCrawlContent:
    return NormalizedCrawlContent(
        body=html,
        visible_text=visible_text,
        content_type="text/html",
        final_url="",
        status_code=200,
        rendered=True,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/crawler/test_fetch_orchestrator.py -k "normalize or map_crawl_failure" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/crawler/content_normalizer.py backend/app/crawler/error_mapping.py backend/app/crawler/schemas/http_fetch.py backend/app/tools/schemas/open_url.py backend/tests/crawler/test_fetch_orchestrator.py
git commit -m "feat: add crawl normalization and error mapping"
```

## Task 5: Add Fetch Orchestrator And Rewire `open_url`

**Files:**
- Create: `backend/app/crawler/fetch_orchestrator.py`
- Modify: `backend/app/tools/open_url.py`
- Modify: `backend/app/crawler/extractor.py`
- Modify: `backend/app/crawler/http_worker.py`
- Modify: `backend/app/crawler/schemas/__init__.py`
- Test: `backend/tests/crawler/test_fetch_orchestrator.py`
- Test: `backend/tests/tools/test_open_url_tool.py`

- [ ] **Step 1: Write the failing orchestrator/tool tests**

```python
from backend.app.tools.schemas.open_url import OpenUrlError, OpenUrlSuccess
from backend.app.tools.open_url import run_open_url


def test_run_open_url_escalates_from_http_403_to_browser_success(fake_orchestrator) -> None:
    payload = run_open_url(
        url="https://en.wikipedia.org/wiki/Agent",
        objective="Find the lead summary",
        fetch_orchestrator=fake_orchestrator,
    )

    result = OpenUrlSuccess.model_validate(payload)
    assert result.strategy_used == "browser"
    assert result.escalation_count == 1
    assert result.challenge_detected is False


def test_run_open_url_returns_typed_failure_when_no_evidence_is_recovered(fake_orchestrator) -> None:
    payload = run_open_url(
        url="https://example.com/login",
        objective="Find the pricing table",
        fetch_orchestrator=fake_orchestrator.with_no_evidence_failure(),
    )

    result = OpenUrlError.model_validate(payload)
    assert result.error.kind == "low_content_quality"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/crawler/test_fetch_orchestrator.py backend/tests/tools/test_open_url_tool.py -k "escalates or no_evidence" -v`
Expected: FAIL because `run_open_url()` does not accept orchestrator injection and still returns success for thin pages

- [ ] **Step 3: Write minimal orchestrator integration**

```python
def run_open_url(
    *,
    url: str,
    objective: str | None = None,
    fetch_orchestrator: FetchOrchestrator | None = None,
) -> OpenUrlToolResult:
    validated_input = OpenUrlInput(url=url, objective=objective)
    orchestrator = fetch_orchestrator or create_fetch_orchestrator()
    orchestrated = orchestrator.run(url=str(validated_input.url), objective=validated_input.objective)
    if orchestrated.error is not None:
        return orchestrated.error
    return _build_crawl_success_payload(
        validated_input=validated_input,
        final_url=orchestrated.final_url,
        extraction_result=orchestrated.extraction_result,
        status_code=orchestrated.status_code,
        content_type=orchestrated.content_type,
        meta=orchestrated.meta,
        strategy_used=orchestrated.strategy_used,
        escalation_count=orchestrated.escalation_count,
        session_profile_id=orchestrated.session_profile_id,
        block_reason=orchestrated.block_reason,
        rendered=orchestrated.rendered,
        challenge_detected=orchestrated.challenge_detected,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/crawler/test_fetch_orchestrator.py backend/tests/tools/test_open_url_tool.py -k "escalates or no_evidence" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/crawler/fetch_orchestrator.py backend/app/tools/open_url.py backend/app/crawler/extractor.py backend/app/crawler/http_worker.py backend/app/crawler/schemas/__init__.py backend/tests/crawler/test_fetch_orchestrator.py backend/tests/tools/test_open_url_tool.py
git commit -m "feat: orchestrate session-aware open_url"
```

## Task 6: Tighten Runtime Source Handling And Zero-Evidence Completion Warnings

**Files:**
- Modify: `backend/agent/runtime_sources.py`
- Modify: `backend/agent/runtime_execution.py`
- Test: `backend/tests/agent/test_runtime.py`

- [ ] **Step 1: Write the failing runtime tests**

```python
from backend.agent.runtime_execution import run_agent_once, RuntimeDependencies


def test_runtime_does_not_register_crawl_source_when_crawl_has_no_evidence() -> None:
    agent = StubAgent(
        raw_result={
            "messages": [
                {
                    "role": "tool",
                    "name": "open_url",
                    "content": {
                        "url": "https://example.com/login",
                        "final_url": "https://example.com/login",
                        "text": "",
                        "markdown": "",
                        "objective": "Find pricing",
                        "excerpts": [],
                        "status_code": 200,
                        "content_type": "text/html",
                        "fallback_reason": "low-content-quality",
                        "strategy_used": "browser",
                        "escalation_count": 1,
                        "session_profile_id": None,
                        "block_reason": "login-gate",
                        "rendered": True,
                        "challenge_detected": False,
                        "meta": {"operation": "open_url", "attempts": 1, "retries": 0, "duration_ms": 12, "timings": {"total_ms": 12}},
                    },
                }
            ],
            "output": "Answer without evidence",
        }
    )

    result = run_agent_once("Find pricing", runtime_dependencies=RuntimeDependencies(agent=agent))

    assert result.sources == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/agent/test_runtime.py -k "no_evidence" -v`
Expected: FAIL because `runtime_sources` still registers crawl success payloads as sources even when they have no evidence text/excerpts

- [ ] **Step 3: Write minimal runtime guardrails**

```python
def has_evidence(self) -> bool:
    return bool(self.excerpts) or bool(self.text.strip())


def register_message_tool_sources(registry: RuntimeSourceRegistry, message: Any) -> None:
    ...
    crawl_result = OpenUrlSuccess.model_validate(payload)
    if not crawl_result.has_evidence():
        return
    source_record = crawl_result.to_source_record()
    registry.register(...)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/agent/test_runtime.py -k "no_evidence" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/agent/runtime_sources.py backend/agent/runtime_execution.py backend/tests/agent/test_runtime.py
git commit -m "fix: block zero-evidence crawl sources"
```

## Task 7: Migrate Schema Imports And Remove Misplaced Top-Level Crawl Schemas

**Files:**
- Modify: `backend/app/schemas/__init__.py`
- Delete: `backend/app/schemas/open_url.py`
- Modify: `backend/app/contracts/open_url.py`
- Modify: any imports found by `rg -n "backend\\.app\\.schemas\\.open_url|from backend\\.app\\.schemas import .*OpenUrl" backend`
- Test: `backend/tests/tools/test_open_url_tool.py`
- Test: `backend/tests/agent/test_runtime.py`

- [ ] **Step 1: Write the failing import regression test**

```python
import importlib
import pytest


def test_legacy_top_level_open_url_schema_module_is_removed() -> None:
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("backend.app.schemas.open_url")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/tools/test_open_url_tool.py -k "legacy_top_level_open_url_schema_module" -v`
Expected: FAIL because `backend.app.schemas.open_url` still exists

- [ ] **Step 3: Write minimal migration cleanup**

```python
# backend/app/contracts/open_url.py
from backend.app.tools.schemas.open_url import (
    OpenUrlError,
    OpenUrlExcerpt,
    OpenUrlInput,
    OpenUrlSuccess,
    OpenUrlToolResult,
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/tools/test_open_url_tool.py -k "legacy_top_level_open_url_schema_module" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/__init__.py backend/app/contracts/open_url.py backend/tests/tools/test_open_url_tool.py
git rm backend/app/schemas/open_url.py
git commit -m "refactor: relocate crawl schemas to feature modules"
```

## Task 8: Full Regression Verification And Container Refresh

**Files:**
- Modify: `backend/tests/crawler/test_http_worker.py` (only if HTTP worker shape changed)
- Modify: `backend/tests/tools/test_open_url_tool.py`
- Modify: `backend/tests/agent/test_runtime.py`
- Docs: `docs/superpowers/plans/2026-03-23-session-aware-web-crawl-design.md` (check boxes only, if you track progress in-repo)

- [ ] **Step 1: Run focused backend test groups**

Run: `pytest backend/tests/crawler/test_session_profiles.py backend/tests/crawler/test_fetch_strategy.py backend/tests/crawler/test_browser_worker.py backend/tests/crawler/test_fetch_orchestrator.py backend/tests/tools/test_open_url_tool.py backend/tests/agent/test_runtime.py -v`
Expected: PASS

- [ ] **Step 2: Run the broader backend regression suite**

Run: `pytest backend/tests -v`
Expected: PASS

- [ ] **Step 3: Rebuild and refresh the backend container**

Run: `docker compose build backend && docker compose up -d backend`
Expected: backend image rebuilds successfully with Playwright dependencies and `/healthz` becomes healthy

- [ ] **Step 4: Smoke-test the live backend**

Run: `docker compose ps backend`
Expected: backend service is `running` and `healthy`

- [ ] **Step 5: Commit and push the final integrated branch**

```bash
git add backend backend/tests docker-compose.yml
git commit -m "feat: ship session-aware open_url pipeline"
git push origin HEAD
```

## Notes For The Implementer

- The Wikipedia regression from the spec should live in `backend/tests/tools/test_open_url_tool.py` or `backend/tests/crawler/test_fetch_orchestrator.py` with a deterministic fake HTTP response that produces an escalation classification instead of relying on live network traffic.
- `open_url` tool description must explicitly describe auto-matched session profiles, browser escalation triggers, and typed failure output once implementation lands.
- If Playwright system packages make `backend/Dockerfile` noisy, keep the install steps isolated and commented sparingly so the file stays readable.
- If `docker-compose.yml` does not need changes after backend rebuild succeeds, do not touch it just to mention browser support.
