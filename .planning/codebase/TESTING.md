# Testing Patterns

**Analysis Date:** 2026-03-24

## Test Framework

**Runner:**
- TypeScript: `vitest` `^4.1.0` from `package.json`
- Python: `pytest` is the active backend runner by usage in `backend/tests/`, but no `pytest.ini` or other pytest config file is present at the repository root
- Config: no `vitest.config.*` or `pytest.ini` detected; TypeScript tests run from `package.json`, and backend test imports are bootstrapped by `backend/tests/conftest.py`

**Assertion Library:**
- TypeScript uses Vitest `expect`, visible in `src/tests/search/search.integration.test.ts`, `src/tests/frontend/state.test.ts`, and `src/tests/frontend-api/run-history.integration.test.ts`
- Python uses plain `assert` and `pytest.raises`, visible in `backend/tests/api/test_agent_run_route.py`, `backend/tests/tools/test_web_search_tool.py`, and `backend/tests/crawler/test_http_worker.py`

**Run Commands:**
```bash
npm run test                 # Run the TypeScript/Vitest suite
npm run test:watch           # Run Vitest in watch mode
pytest backend/tests -q      # Common backend command used by the repo's backend test layout
```

## Test File Organization

**Location:**
- TypeScript tests live under `src/tests/` in domain folders that mirror runtime areas: `src/tests/search/`, `src/tests/fetch/`, `src/tests/frontend-api/`, `src/tests/frontend/`, `src/tests/core/`, and `src/tests/safety/`
- Python tests live under `backend/tests/` in matching domains: `backend/tests/agent/`, `backend/tests/api/`, `backend/tests/crawler/`, `backend/tests/core/`, and `backend/tests/tools/`

**Naming:**
- TypeScript uses `*.test.ts` with scope in the filename, such as `src/tests/fetch/fetch.reliability.test.ts` and `src/tests/frontend-api/runs.stream.test.ts`
- Python uses pytest-style `test_*.py`, such as `backend/tests/test_startup_settings.py` and `backend/tests/tools/test_web_crawl_tool.py`

**Structure:**
```text
src/tests/
  core/
  fetch/
  frontend/
  frontend-api/
  safety/
  search/
backend/tests/
  agent/
  api/
  core/
  crawler/
  tools/
```

## Test Structure

**Suite Organization:**
```typescript
describe("Serper transport", () => {
  beforeEach(() => {
    requestMock.mockReset();
    vi.resetModules();
  });

  it("retries 429 and succeeds with validated provider payload", async () => {
    const { callSerperSearch } = await import("../../providers/serper/client.js");

    requestMock
      .mockResolvedValueOnce(createResponse(429, { message: "rate limited" }))
      .mockResolvedValueOnce(createResponse(200, { organic: [] }));

    await expect(
      callSerperSearch("test query", { limit: 5 }, { apiKey: "test-key" }),
    ).resolves.toMatchObject({
      meta: { attempts: 2, retries: 1 },
    });
  });
});
```

```python
def test_run_request_contract_rejects_blank_prompt() -> None:
    with pytest.raises(ValidationError, match="prompt must not be empty"):
        AgentRunRequest(prompt="   ", mode="agentic")
```

**Patterns:**
- Group tests by behavior and boundary rather than by class name. Examples: `src/tests/search/search.integration.test.ts`, `src/tests/fetch/fetch.safety-compliance.integration.test.ts`, and `backend/tests/api/test_agent_run_route.py`.
- Normalize inputs and assert the fully normalized output contract, not just one field. This is especially common in `src/tests/setup.test.ts`, `src/tests/frontend-api/routes.contracts.test.ts`, and `backend/tests/api/test_agent_run_route.py`.
- Check machine-readable metadata on success and failure paths, including retries, duration, event ordering, and structured citations. Examples appear in `src/tests/core/reliability/execute-with-retry.test.ts`, `src/tests/frontend-api/run-history.integration.test.ts`, and `backend/tests/tools/test_web_search_tool.py`.

## Mocking

**Framework:** Vitest `vi.*` in TypeScript; `monkeypatch`, inline stubs, and fake callables in pytest

**Patterns:**
```typescript
const requestMock = vi.fn();

vi.mock("undici", () => ({
  request: requestMock,
}));

beforeEach(() => {
  requestMock.mockReset();
  vi.resetModules();
});
```

```python
monkeypatch.setattr(
    agent_run_service,
    "run_agent_once",
    lambda prompt, mode, retrieval_policy: AgentRunResult(
        run_id="run-quick",
        status="completed",
        final_answer={"text": "Quick answer."},
        tool_call_count=1,
        elapsed_ms=10,
    ),
)
```

**What to Mock:**
- Network edges and SDK/provider calls are mocked heavily: `undici` in `src/tests/search/search.integration.test.ts`, frontend SDK calls in `src/tests/frontend-api/routes.contracts.test.ts`, and HTTP workers or Serper clients in `backend/tests/tools/test_web_crawl_tool.py` and `backend/tests/tools/test_web_search_tool.py`
- Long-running or external agent behavior is replaced with explicit stubs/dataclasses in `backend/tests/agent/test_runtime.py`
- Environment and settings are isolated with `monkeypatch.setenv` and `get_settings.cache_clear()` in `backend/tests/api/test_agent_run_route.py` and `backend/tests/test_startup_settings.py`

**What NOT to Mock:**
- Validation layers are usually exercised for real. Tests instantiate `AgentRunRequest`, `WebSearchResponse`, `WebCrawlBatchSuccess`, and Zod schemas directly in `backend/tests/api/test_agent_run_route.py`, `backend/tests/tools/test_web_search_tool.py`, `backend/tests/tools/test_web_crawl_tool.py`, and `src/tests/frontend-api/run-events.contracts.test.ts`
- Reducers and normalization helpers are typically tested without mocks, such as `src/tests/frontend/state.test.ts`, `src/core/policy/retrieval-controls.test.ts`, and `backend/tests/core/test_retry.py`

## Fixtures and Factories

**Test Data:**
```typescript
const DEFAULT_RETRIEVAL_POLICY = {
  search: {
    country: "US",
    language: "en",
    freshness: "any",
    domainScope: {
      includeDomains: [],
      excludeDomains: [],
    },
  },
  fetch: {
    maxAgeMs: 300_000,
    fresh: false,
  },
} as const;
```

```python
class StubRuntimeRunner:
    def __init__(self, result: AgentRunResult) -> None:
        self.result = result
        self.calls: list[tuple[str, AgentRunMode, AgentRunRetrievalPolicy]] = []
```

**Location:**
- Static fixtures are stored under `src/tests/fixtures/`, including `src/tests/fixtures/serper/organic.json`, `src/tests/fixtures/robots/allow-all.txt`, `src/tests/fixtures/robots/deny-path.txt`, and `src/tests/fixtures/fetch/article.html`
- Python tests rely more on inline factories, stub classes, and helper functions inside each test module than on shared fixture directories
- The only shared backend fixture file is `backend/tests/conftest.py`, and it exists solely to add the repo root to `sys.path`

## Coverage

**Requirements:** No coverage threshold or enforcement config was detected. There is no coverage script in `package.json` and no pytest coverage configuration file in the repo root.

**View Coverage:**
```bash
Not configured in the repository
```

## Test Types

**Unit Tests:**
- Pure logic and validation tests are common in `src/tests/core/reliability/execute-with-retry.test.ts`, `src/core/policy/retrieval-controls.test.ts`, `src/tests/frontend/state.test.ts`, `backend/tests/core/test_retry.py`, and schema-focused cases in `backend/tests/tools/test_web_search_tool.py`

**Integration Tests:**
- TypeScript integration tests usually wire together a real module boundary with mocked transport or I/O seams, such as `src/tests/search/search.integration.test.ts`, `src/tests/fetch/fetch.safety-compliance.integration.test.ts`, `src/tests/fetch-controls.integration.test.ts`, and `src/tests/frontend-api/run-history.integration.test.ts`
- Python integration-style tests exercise FastAPI routes, tools, or crawler flows against real schema validation and stubbed dependencies in `backend/tests/api/test_agent_run_route.py`, `backend/tests/crawler/test_fetch_orchestrator.py`, and `backend/tests/tools/test_web_crawl_tool.py`

**E2E Tests:**
- No browser-driven or multi-service E2E framework is currently present in the main repo test suite
- The closest end-to-end behavior coverage is the frontend API and stream harness in `src/tests/frontend-api/run-history.integration.test.ts` and `src/tests/frontend-api/runs.stream.test.ts`

## Common Patterns

**Async Testing:**
```typescript
await expect(
  callSerperSearch("test query", undefined, { apiKey: "test-key" }),
).rejects.toMatchObject({
  kind: "invalid_request",
  retryable: false,
});
```

```python
response = agent_run_service.execute_agent_run_request(
    AgentRunRequest(prompt="Find one source", mode="quick")
)

assert isinstance(response, AgentRunSuccessResponse)
assert response.status == "completed"
```

**Error Testing:**
```typescript
const envelope = SearchApiEnvelopeSchema.parse(response.json);
expect(envelope.ok).toBe(false);
if (envelope.ok) {
  throw new Error("Expected search SDK failure envelope.");
}
expect(envelope.error.code).toBe("RATE_LIMITED");
```

```python
with pytest.raises(ValidationError) as exc_info:
    WebSearchResponse(**payload)

assert "result_count" in str(exc_info.value)
```

## Visible Gaps

- Backend tests are extensive around tools, crawler flows, runtime routing, and API contracts, but there is no visible backend coverage for persistence/storage concerns beyond `backend/agent/deep_research_store.py`
- TypeScript tests are strong around SDK, policy, safety, and frontend API contracts, but there is no UI browser automation covering `public/index.html` plus `src/frontend/client/app.ts`
- No coverage reporting or minimum thresholds are configured, so regressions are prevented by case selection rather than enforced percentages
- Python test setup is intentionally minimal; there are no shared fixture factories for backend domains beyond `backend/tests/conftest.py`, so repeated stub patterns remain duplicated across modules

---

*Testing analysis: 2026-03-24*
