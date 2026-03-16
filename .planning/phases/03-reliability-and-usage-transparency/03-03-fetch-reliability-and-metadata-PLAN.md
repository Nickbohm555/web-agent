---
phase: 03-reliability-and-usage-transparency
plan: 03
type: execute
wave: 2
depends_on: ["03-01"]
files_modified:
  - src/scraper/http-worker.ts
  - src/scraper/orchestrator.ts
  - src/sdk/fetch.ts
  - src/tests/fetch/fetch.reliability.test.ts
  - src/tests/fetch/fetch.meta.test.ts
autonomous: true
must_haves:
  truths:
    - "Fetch retries transient failures deterministically and honors rate-limit retry semantics."
    - "Fetch returns stable typed error categories for non-retryable failures."
    - "Successful fetch responses expose inspectable per-call usage and timing metadata."
  artifacts:
    - path: "src/scraper/http-worker.ts"
      provides: "HTTP retrieval path integrated with shared deterministic retry/error mapping"
    - path: "src/scraper/orchestrator.ts"
      provides: "Fetch orchestration that propagates typed errors and reliability context"
    - path: "src/sdk/fetch.ts"
      provides: "Public fetch method returning normalized content and `meta` contract"
    - path: "src/tests/fetch/fetch.reliability.test.ts"
      provides: "Deterministic retry and typed error coverage for fetch flow"
    - path: "src/tests/fetch/fetch.meta.test.ts"
      provides: "Fetch metadata shape and semantics assertions"
  key_links:
    - from: "src/scraper/http-worker.ts"
      to: "src/core/reliability/execute-with-retry.ts"
      via: "HTTP attempt wrapper for retryable transient failures"
      pattern: "executeWithRetry|withRetry"
    - from: "src/scraper/orchestrator.ts"
      to: "src/core/errors/sdk-error.ts"
      via: "typed failure propagation and fallback reason classification"
      pattern: "kind|retryable"
    - from: "src/sdk/fetch.ts"
      to: "src/core/telemetry/call-meta.ts"
      via: "final metadata generation in fetch response"
      pattern: "buildCallMeta|finalizeMeta"
---

<objective>
Wire Phase 3 reliability and metadata guarantees into the full `fetch(...)` execution path.

Purpose: Fulfill REL-01/REL-02 for fetch so callers get deterministic failure handling and inspectable operational metadata without provider internals leaking out.
Output: Fetch worker/orchestrator/SDK integration with shared retry/error/meta modules and focused reliability/metadata tests.
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
@.planning/phases/01-core-retrieval-engine/01-03-fetch-http-first-slice-PLAN.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Route fetch HTTP path through shared deterministic reliability executor</name>
  <files>src/scraper/http-worker.ts, src/tests/fetch/fetch.reliability.test.ts</files>
  <action>Integrate the HTTP-first worker with `src/core/reliability/execute-with-retry.ts` and canonical error mapper from Phase 03-01. Ensure transient network/timeout/429/selected 5xx failures follow deterministic retry policy and Retry-After precedence where available. Ensure policy-denied and other non-retryable failures abort immediately with stable typed errors. Add tests that verify deterministic attempt/retry counts and typed terminal errors for non-retryable scenarios.</action>
  <verify>`npm run test -- src/tests/fetch/fetch.reliability.test.ts` passes with deterministic retry schedule and typed error assertions.</verify>
  <done>Fetch worker reliability behavior is deterministic, bounded, and aligned with shared error taxonomy.</done>
</task>

<task type="auto">
  <name>Task 2: Propagate typed errors and metadata through fetch orchestrator and SDK</name>
  <files>src/scraper/orchestrator.ts, src/sdk/fetch.ts, src/tests/fetch/fetch.meta.test.ts</files>
  <action>Update orchestrator + SDK fetch path to propagate canonical typed errors without leaking raw transport/provider payloads. Collect call-level attempts/retries/cache/timing data and emit response `meta` using `src/core/telemetry/call-meta.ts`. Keep fallback reason semantics explicit and stable alongside typed error categories. Add metadata tests confirming required `meta` fields and structured timing/usage values are exposed programmatically on successful responses.</action>
  <verify>`npm run test -- src/tests/fetch/fetch.meta.test.ts && npm run typecheck` both pass.</verify>
  <done>Successful `fetch(...)` responses include stable metadata and failure exits are typed/actionable for caller logic.</done>
</task>

<task type="auto">
  <name>Task 3: Validate fetch reliability + metadata behavior across representative scenarios</name>
  <files>src/tests/fetch/fetch.reliability.test.ts, src/tests/fetch/fetch.meta.test.ts</files>
  <action>Expand scenario coverage to include: transient failure then success, deterministic non-retryable terminal failure, and success path metadata emission with inspectable operation counters/timings. Keep assertions deterministic for attempts/retries and category fields; avoid brittle exact timestamp matching. Ensure tests reflect HTTP-first flow and do not introduce browser-first logic.</action>
  <verify>`npm run test -- src/tests/fetch/fetch.reliability.test.ts src/tests/fetch/fetch.meta.test.ts` passes consistently across reruns.</verify>
  <done>REL-01 and REL-02 are verified for fetch at the public SDK boundary.</done>
</task>

</tasks>

<verification>
Run `npm run test -- src/tests/fetch/fetch.reliability.test.ts src/tests/fetch/fetch.meta.test.ts` and `npm run typecheck`.
</verification>

<success_criteria>
- Fetch path uses shared deterministic retry/error behavior.
- Fetch non-retryable failures return stable typed categories.
- Fetch success responses expose required per-call usage/timing metadata.
</success_criteria>

<output>
After completion, create `.planning/phases/03-reliability-and-usage-transparency/03-03-SUMMARY.md`
</output>
