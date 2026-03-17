---
phase: 02-search-and-crawl-tool-capability
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/app/contracts/tool_errors.py
  - backend/app/contracts/web_search.py
  - backend/app/core/retry.py
  - backend/app/providers/serper_client.py
  - backend/app/tools/web_search.py
  - backend/tests/tools/test_web_search_tool.py
  - backend/requirements.txt
autonomous: true
user_setup:
  - service: serper
    why: "Live integration checks require a real provider API key."
    env_vars:
      - name: SERPER_API_KEY
        source: "Serper dashboard API keys page"
must_haves:
  truths:
    - "Tool `web_search` returns normalized result entries (title, url, snippet, rank) for a valid query."
    - "Transient provider/network failures are retried with bounded attempts and surfaced with retry metadata."
    - "Non-retryable failures return explicit structured errors instead of empty result sets."
  artifacts:
    - path: "backend/app/tools/web_search.py"
      provides: "LangChain `@tool(\"web_search\")` adapter with strict args schema and contract-valid return shape."
      exports: ["web_search", "WebSearchInput"]
    - path: "backend/app/providers/serper_client.py"
      provides: "Serper transport client with deterministic normalization and retry classification hooks."
    - path: "backend/app/contracts/web_search.py"
      provides: "Pydantic request/response contracts for search outputs."
    - path: "backend/app/contracts/tool_errors.py"
      provides: "Shared typed error envelope used by tool responses."
    - path: "backend/tests/tools/test_web_search_tool.py"
      provides: "Contract and reliability regression coverage for search tool behavior."
  key_links:
    - from: "backend/app/tools/web_search.py"
      to: "backend/app/providers/serper_client.py"
      via: "tool adapter service call"
      pattern: "serper|search"
    - from: "backend/app/providers/serper_client.py"
      to: "backend/app/contracts/web_search.py"
      via: "provider payload mapping into response model"
      pattern: "result_count|rank|provider_position"
    - from: "backend/app/providers/serper_client.py"
      to: "backend/app/core/retry.py"
      via: "bounded retry policy wrapper"
      pattern: "retry|attempts|429|5.."
---

<objective>
Implement a Serper-backed Python `web_search` tool with strict schemas, deterministic result normalization, and debuggable error/retry metadata.

Purpose: Delivers `AGENT-02` so the runtime can reliably gather external links/snippets without leaking provider payloads or hiding failures.
Output: Search contracts, Serper client, tool adapter, retry/error plumbing, and tests proving success + error paths.
</objective>

<execution_context>
@~/.cursor/get-shit-done/workflows/execute-plan.md
@~/.cursor/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/REQUIREMENTS.md
@.planning/phases/02-search-and-crawl-tool-capability/02-RESEARCH.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Define shared tool-error and web-search response contracts</name>
  <files>backend/app/contracts/tool_errors.py, backend/app/contracts/web_search.py</files>
  <action>Create strict Pydantic v2 models for: search input args (`query`, `max_results` bounded), normalized search result item (`title`, `url`, `snippet`, `rank` with `position` + optional `provider_position`), search success envelope (`query`, `results`, `metadata`, `meta`), and shared error envelope (`kind`, `message`, `retryable`, optional `status_code`, `attempt_number`, `operation`, `timings`). Do not expose raw Serper field names in outward contracts. Ensure models are reusable by future tool implementations and tests.</action>
  <verify>Run backend tests that instantiate each model with valid/invalid payloads and confirm validation behavior is deterministic.</verify>
  <done>Search and error contracts exist as importable typed models with explicit validation guarantees.</done>
</task>

<task type="auto">
  <name>Task 2: Implement Serper client with bounded retry and deterministic normalization</name>
  <files>backend/app/core/retry.py, backend/app/providers/serper_client.py, backend/requirements.txt</files>
  <action>Add retry utility using `tenacity` with max 3 attempts and exponential backoff for retryable classes only (`httpx.RequestError`, timeout/reset, HTTP 429, HTTP 5xx). Implement Serper client call using `httpx` POST with API key header, strict timeout, and response mapping into normalized result list sorted by provider order into deterministic `rank.position`. Fail fast on non-retryable 4xx. Add required dependencies for search path if missing (`httpx`, `tenacity`, `pydantic`). Keep sensitive values out of logs/errors.</action>
  <verify>Run unit tests with mocked HTTP responses for 200, 429->200 retry recovery, 500 terminal failure, and 400 fail-fast behavior.</verify>
  <done>Serper transport path produces normalized contract-valid results and typed retryable/non-retryable failure outcomes.</done>
</task>

<task type="auto">
  <name>Task 3: Expose `web_search` LangChain tool and lock behavior with contract tests</name>
  <files>backend/app/tools/web_search.py, backend/tests/tools/test_web_search_tool.py</files>
  <action>Create `@tool(\"web_search\")` adapter with args schema model and snake_case name exactly matching roadmap requirement. Tool should delegate to Serper client and always return either a contract-valid success object or a contract-valid error object (no silent empty array fallbacks, no uncaught raw traceback in response body). Add tests that validate success shape, deterministic rank ordering, and explicit error envelope fields (`kind`, `retryable`, `operation`, `attempt_number/meta attempts`) across failure scenarios.</action>
  <verify>Run `pytest backend/tests/tools/test_web_search_tool.py` and confirm all contract + reliability cases pass.</verify>
  <done>`web_search` is callable as a LangChain tool and returns stable normalized outputs with explicit, debuggable failure semantics.</done>
</task>

</tasks>

<verification>
1. Run `pytest backend/tests/tools/test_web_search_tool.py`.
2. Run backend-wide targeted tests (or project equivalent) for provider/contract modules.
3. Optionally run one live smoke call with `SERPER_API_KEY` set to verify non-mocked response mapping still satisfies the contract schema.
</verification>

<success_criteria>
- `web_search` produces normalized links/snippets contract required by Phase 2 success criterion #1.
- Retry policy behavior is bounded and visible in metadata/error fields.
- Failure modes are explicit and machine-readable, satisfying Phase 2 success criterion #3 for search path.
</success_criteria>

<output>
After completion, create `.planning/phases/02-search-and-crawl-tool-capability/02-01-SUMMARY.md`
</output>
