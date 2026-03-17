---
phase: 02-search-and-crawl-tool-capability
plan: 02
type: execute
wave: 2
depends_on: ["02-01"]
files_modified:
  - backend/app/contracts/web_crawl.py
  - backend/app/crawler/http_worker.py
  - backend/app/crawler/extractor.py
  - backend/app/tools/web_crawl.py
  - backend/tests/tools/test_web_crawl_tool.py
  - backend/requirements.txt
autonomous: true
must_haves:
  truths:
    - "Tool `web_crawl` can fetch a URL and return extracted text/markdown in a stable response shape."
    - "Low-content or unsupported-content cases are surfaced with explicit fallback reason rather than silent success."
    - "Network/HTTP failures return structured, debuggable error payloads with retry metadata."
  artifacts:
    - path: "backend/app/contracts/web_crawl.py"
      provides: "Pydantic contracts for crawl success payload, fallback states, and metadata."
      exports: ["WebCrawlInput", "WebCrawlSuccess", "WebCrawlError"]
    - path: "backend/app/crawler/http_worker.py"
      provides: "HTTP-first URL retrieval with timeout, redirect handling, and retryable error classification."
    - path: "backend/app/crawler/extractor.py"
      provides: "Trafilatura extraction pipeline yielding deterministic `text`/`markdown` + quality state."
    - path: "backend/app/tools/web_crawl.py"
      provides: "LangChain `@tool(\"web_crawl\")` adapter returning contract-valid success/error envelopes."
    - path: "backend/tests/tools/test_web_crawl_tool.py"
      provides: "Regression tests for crawl success, fallback reasons, and explicit error channels."
  key_links:
    - from: "backend/app/tools/web_crawl.py"
      to: "backend/app/crawler/http_worker.py"
      via: "tool call into fetch worker"
      pattern: "fetch|http_worker"
    - from: "backend/app/crawler/http_worker.py"
      to: "backend/app/crawler/extractor.py"
      via: "HTML response body passed into extractor"
      pattern: "extract|markdown|text"
    - from: "backend/app/tools/web_crawl.py"
      to: "backend/app/contracts/web_crawl.py"
      via: "response shaping into typed envelope"
      pattern: "fallback_reason|status_code|content_type"
---

<objective>
Implement an in-house Python `web_crawl` tool that performs HTTP-first retrieval and deterministic content extraction with explicit fallback/error states.

Purpose: Delivers `AGENT-03` while preserving debuggability and consistent tool contracts for downstream LangGraph orchestration.
Output: Crawl contracts, HTTP worker, extraction module, tool adapter, and tests covering success + failure/fallback paths.
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
@.planning/phases/02-search-and-crawl-tool-capability/02-01-implement-serper-backed-web-search-tool-in-python-PLAN.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Define crawl contracts and HTTP-first worker behavior</name>
  <files>backend/app/contracts/web_crawl.py, backend/app/crawler/http_worker.py, backend/requirements.txt</files>
  <action>Create strict Pydantic models for crawl input and output fields required by roadmap/research (`url`, `final_url`, `text`, `markdown`, `status_code`, `content_type`, `fallback_reason`, `meta`, plus shared error envelope). Implement HTTP worker using `httpx` with bounded retry for transient failures only, redirect support, and content-type inspection. Keep max response size guardrails explicit and return typed failure mapping for non-html or terminal status cases. Add required dependencies if missing (`trafilatura`, `httpx`, `tenacity`).</action>
  <verify>Run unit tests with mocked HTTP responses covering html 200, redirect final URL capture, unsupported content type, timeout/retry behavior, and terminal 4xx error classification.</verify>
  <done>Crawl fetch path produces deterministic typed fetch outcomes and classifies retryable vs terminal failures correctly.</done>
</task>

<task type="auto">
  <name>Task 2: Implement extraction state machine and fallback reason mapping</name>
  <files>backend/app/crawler/extractor.py, backend/app/contracts/web_crawl.py</files>
  <action>Implement Trafilatura-based extraction that returns both markdown and plain text outputs. Encode extraction outcomes as explicit states: `ok`, `low-content-quality`, `unsupported-content-type`, `network-error`. Use deterministic quality threshold (seed from research recommendation, e.g. >=120 text chars) and map low-quality/empty extraction to `fallback_reason=\"low-content-quality\"` (not success with empty values). Preserve final response shape regardless of state.</action>
  <verify>Run extraction-focused tests with representative HTML fixtures for rich content, boilerplate-only content, and non-HTML payload handling.</verify>
  <done>Extraction results are never silently empty; every non-success case has explicit state and fallback reason.</done>
</task>

<task type="auto">
  <name>Task 3: Expose `web_crawl` LangChain tool and prove contract via tests</name>
  <files>backend/app/tools/web_crawl.py, backend/tests/tools/test_web_crawl_tool.py</files>
  <action>Create `@tool(\"web_crawl\")` with strict args schema and snake_case name. Wire tool flow `validate input -> HTTP worker -> extractor -> contract response` and enforce shared error envelope compatibility from Plan 02-01. Add tests for: successful extraction, redirect with `final_url`, unsupported content type fallback, low-content-quality fallback, and explicit retry/error metadata (`kind`, `retryable`, `operation`, attempts/timings) on failures. Do not return provider/raw exception payloads directly.</action>
  <verify>Run `pytest backend/tests/tools/test_web_crawl_tool.py` and ensure all success + fallback + error assertions pass.</verify>
  <done>`web_crawl` is callable with stable output schema and explicit failure semantics, satisfying Phase 2 crawl + debuggability goals.</done>
</task>

</tasks>

<verification>
1. Run `pytest backend/tests/tools/test_web_crawl_tool.py`.
2. Run targeted backend tests to ensure shared contracts from Plan 02-01 still pass.
3. Optionally execute one live crawl against a known HTML URL and one non-HTML URL to confirm fallback reason behavior in real responses.
</verification>

<success_criteria>
- `web_crawl` returns consistent extracted content payloads required by Phase 2 success criterion #2.
- Low-content/unsupported/network edge cases are explicit and debuggable instead of silent failures.
- Tool error and metadata envelopes remain aligned with the shared reliability contract introduced in Plan 02-01.
</success_criteria>

<output>
After completion, create `.planning/phases/02-search-and-crawl-tool-capability/02-02-SUMMARY.md`
</output>
