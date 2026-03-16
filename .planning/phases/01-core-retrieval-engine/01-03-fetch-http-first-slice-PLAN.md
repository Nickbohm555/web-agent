---
phase: 01-core-retrieval-engine
plan: 03
type: execute
wave: 2
depends_on: ["01-01"]
files_modified:
  - src/scraper/robots.ts
  - src/scraper/http-worker.ts
  - src/scraper/extract.ts
  - src/scraper/orchestrator.ts
  - src/sdk/fetch.ts
  - src/tests/fixtures/fetch/article.html
  - src/tests/fetch/fetch.unit.test.ts
  - src/tests/fetch/fetch.stability.test.ts
autonomous: true
must_haves:
  truths:
    - "Calling `fetch(url, options)` returns clean content in one consistent response shape."
    - "Fetch flow attempts HTTP extraction first and exposes explicit fallback reasons when escalation is needed."
    - "Equivalent fetch inputs and equivalent source content produce stable response structure across repeated runs."
  artifacts:
    - path: "src/scraper/orchestrator.ts"
      provides: "HTTP-first orchestration with robots/politeness gate and explicit fallback reason handling"
    - path: "src/scraper/extract.ts"
      provides: "Content extraction and normalization to text/markdown outputs"
    - path: "src/sdk/fetch.ts"
      provides: "Public fetch orchestration with contract validation"
    - path: "src/tests/fetch/fetch.stability.test.ts"
      provides: "Stability assertions for repeated equivalent fetch executions"
  key_links:
    - from: "src/sdk/fetch.ts"
      to: "src/scraper/orchestrator.ts"
      via: "fetch execution path"
      pattern: "runFetchOrchestrator|orchestrateFetch"
    - from: "src/scraper/orchestrator.ts"
      to: "src/scraper/robots.ts"
      via: "pre-fetch policy gate"
      pattern: "evaluateRobots|isAllowed"
    - from: "src/scraper/orchestrator.ts"
      to: "src/scraper/extract.ts"
      via: "HTTP response extraction pipeline"
      pattern: "extract(Content|Main)"
---

<objective>
Implement the complete Phase 01 fetch slice with HTTP-first extraction and stable normalized output behavior.

Purpose: Satisfy CORE-02 while enforcing explicit flow control (robots gate, extraction normalization, fallback reasoning) and response stability.
Output: Working `fetch(...)` path with deterministic response contract and focused fetch stability tests.
</objective>

<execution_context>
@~/.cursor/get-shit-done/workflows/execute-plan.md
@~/.cursor/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/REQUIREMENTS.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/01-core-retrieval-engine/01-RESEARCH.md
@.planning/phases/01-core-retrieval-engine/01-01-SUMMARY.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Build robots/politeness gate and HTTP worker</name>
  <files>src/scraper/robots.ts, src/scraper/http-worker.ts</files>
  <action>Implement robots evaluation and politeness handling as the first stage of fetch execution. Parse `robots.txt` with `robots-parser`, evaluate allow/deny for configured user-agent, and expose machine-readable policy outcomes. Implement HTTP worker using `undici` with bounded timeout/retry integration (via shared core helpers) and no browser-first behavior. Return explicit worker result states that orchestrator can interpret (`OK`, `NETWORK_ERROR`, `HTTP_STATUS_UNSUPPORTED`, etc.).</action>
  <verify>`npm run test -- src/tests/fetch/fetch.unit.test.ts` passes checks that disallowed robots paths are blocked before outbound content fetch and retry rules remain bounded.</verify>
  <done>Fetch pipeline has deterministic preflight gating and HTTP retrieval behavior, with explicit typed outcomes.</done>
</task>

<task type="auto">
  <name>Task 2: Implement extraction + HTTP-first orchestrator and SDK wiring</name>
  <files>src/scraper/extract.ts, src/scraper/orchestrator.ts, src/sdk/fetch.ts</files>
  <action>Implement HTML extraction pipeline using `cheerio` + `@mozilla/readability` and normalize output into contract shape (text/markdown channels, metadata, fallback reason). Orchestrator must run in this order: policy gate -> HTTP fetch -> extraction -> fallback decision. Add explicit fallback reason enum values (`NETWORK_ERROR`, `LOW_CONTENT_QUALITY`, etc.) but keep browser fallback as a structured stub path (no browser-first implementation). Replace placeholder `src/sdk/fetch.ts` with full contract-validated orchestration.</action>
  <verify>`npm run test -- src/tests/fetch/fetch.unit.test.ts` passes assertions for output shape consistency and explicit fallback reasons by scenario.</verify>
  <done>`fetch(url, options)` returns clean content in a consistent response shape and enforces HTTP-first orchestration semantics.</done>
</task>

<task type="auto">
  <name>Task 3: Add fetch stability fixtures and repeated-run tests</name>
  <files>src/tests/fixtures/fetch/article.html, src/tests/fetch/fetch.stability.test.ts</files>
  <action>Create representative HTML fixture(s) and repeated-run tests that execute equivalent fetch inputs against fixed fixture responses multiple times, asserting stable normalized response shape and deterministic metadata fields. Include edge case for low-content extraction to confirm fallback reason determinism. Avoid asserting brittle timestamps; assert stable contract fields and structured outcome categories.</action>
  <verify>`npm run test -- src/tests/fetch/fetch.stability.test.ts && npm run typecheck && npm run build` all pass.</verify>
  <done>CORE-02 and Phase 01 stability requirement are validated for fetch through deterministic fixture-driven tests.</done>
</task>

</tasks>

<verification>
Run full gate at end of plan: `npm run typecheck`, `npm run test`, `npm run build`.
</verification>

<success_criteria>
- Public `fetch(...)` contract remains consistent across success/fallback paths.
- HTTP-first flow is enforced with robots/politeness gate before extraction.
- Repeated equivalent runs preserve stable normalized structure and fallback reason categories.
</success_criteria>

<output>
After completion, create `.planning/phases/01-core-retrieval-engine/01-03-SUMMARY.md`
</output>
