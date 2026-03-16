---
phase: 03-reliability-and-usage-transparency
plan: 02
type: execute
wave: 2
depends_on: ["03-01"]
files_modified:
  - src/providers/serper/client.ts
  - src/sdk/search.ts
  - src/tests/search/search.reliability.test.ts
  - src/tests/search/search.meta.test.ts
autonomous: true
must_haves:
  truths:
    - "Search retries retryable failures deterministically, including rate-limit scenarios."
    - "Search returns stable typed non-retryable error categories for actionable handling."
    - "Successful search responses include inspectable per-call usage and timing metadata."
  artifacts:
    - path: "src/providers/serper/client.ts"
      provides: "Serper transport wired through shared retry executor and typed error mapping"
    - path: "src/sdk/search.ts"
      provides: "Search orchestration returning normalized result contract with `meta`"
    - path: "src/tests/search/search.reliability.test.ts"
      provides: "Deterministic retry/error behavior tests for search flow"
    - path: "src/tests/search/search.meta.test.ts"
      provides: "Search metadata shape and semantics assertions"
  key_links:
    - from: "src/providers/serper/client.ts"
      to: "src/core/reliability/execute-with-retry.ts"
      via: "provider call wrapped in shared retry executor"
      pattern: "executeWithRetry|withRetry"
    - from: "src/sdk/search.ts"
      to: "src/core/telemetry/call-meta.ts"
      via: "final response meta generation"
      pattern: "buildCallMeta|finalizeMeta"
    - from: "src/sdk/search.ts"
      to: "src/core/errors/sdk-error.ts"
      via: "typed error propagation to caller"
      pattern: "kind|retryable"
---

<objective>
Wire Phase 3 reliability and metadata guarantees into the full `search(...)` execution path.

Purpose: Fulfill REL-01/REL-02 for search with deterministic retry/error behavior and inspectable per-call operational metadata.
Output: Search provider + SDK orchestration using shared reliability modules, with dedicated reliability and metadata tests.
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
@.planning/phases/03-reliability-and-usage-transparency/03-RESEARCH.md
@.planning/phases/03-reliability-and-usage-transparency/03-01-SUMMARY.md
@.planning/phases/01-core-retrieval-engine/01-02-search-serper-slice-PLAN.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Route Serper calls through shared deterministic reliability layer</name>
  <files>src/providers/serper/client.ts, src/tests/search/search.reliability.test.ts</files>
  <action>Replace any local retry logic with `src/core/reliability/execute-with-retry.ts` so all transient failure handling is centralized. Ensure `429`, `5xx`, and retryable transport failures follow deterministic retry/backoff behavior, honoring `Retry-After` first when provided. Map terminal failures to canonical typed SDK errors from Phase 03-01. Add search transport tests that assert deterministic attempt counts and correct typed outcomes for retryable vs non-retryable cases.</action>
  <verify>`npm run test -- src/tests/search/search.reliability.test.ts` passes with deterministic retry assertions and typed error checks.</verify>
  <done>Search transport reliability behavior is centralized, deterministic, and contract-stable.</done>
</task>

<task type="auto">
  <name>Task 2: Emit search call metadata through SDK response contract</name>
  <files>src/sdk/search.ts, src/tests/search/search.meta.test.ts</files>
  <action>Update search orchestration to collect attempts/retries/cache/timing information from the shared reliability + policy/cache layers and populate response `meta` using `src/core/telemetry/call-meta.ts`. Keep response payload normalized (`title`, `url`, `snippet`, rank metadata) and keep provider internals private. Include metadata tests asserting required fields are present, numeric timing fields are non-negative, and operation-specific counters remain programmatically inspectable.</action>
  <verify>`npm run test -- src/tests/search/search.meta.test.ts && npm run typecheck` both pass.</verify>
  <done>Successful `search(...)` responses expose stable, inspectable operational metadata satisfying REL-02 for search.</done>
</task>

<task type="auto">
  <name>Task 3: Validate end-to-end search reliability + metadata behavior</name>
  <files>src/sdk/search.ts, src/tests/search/search.reliability.test.ts, src/tests/search/search.meta.test.ts</files>
  <action>Add or extend integration-style tests that exercise full search flow under: (1) transient retry then success, (2) non-retryable failure, and (3) success with metadata emission. Verify that typed errors are stable and that metadata values remain deterministic where expected (attempt/retry counts) while avoiding brittle wall-clock exact-value assertions for duration fields.</action>
  <verify>`npm run test -- src/tests/search/search.reliability.test.ts src/tests/search/search.meta.test.ts` passes consistently across repeated runs.</verify>
  <done>REL-01 and REL-02 are demonstrably satisfied for search at SDK boundary level.</done>
</task>

</tasks>

<verification>
Run `npm run test -- src/tests/search/search.reliability.test.ts src/tests/search/search.meta.test.ts` and `npm run typecheck`.
</verification>

<success_criteria>
- Search path uses the shared deterministic retry/error pipeline.
- Search surfaces stable typed error categories for non-retryable outcomes.
- Search response includes required per-call metadata fields with programmatic inspectability.
</success_criteria>

<output>
After completion, create `.planning/phases/03-reliability-and-usage-transparency/03-02-SUMMARY.md`
</output>
