---
phase: 02-retrieval-controls-and-cost-tuning
plan: 03
type: execute
wave: 2
depends_on:
  - "02-01"
files_modified:
  - src/sdk/contracts/fetch.ts
  - src/sdk/fetch.ts
  - src/core/cache/fetch-cache.ts
  - src/core/cache/fetch-cache.test.ts
  - src/tests/fetch-controls.integration.test.ts
autonomous: true
must_haves:
  truths:
    - "A developer can choose cached vs fresh fetch behavior with explicit cache controls."
    - "Force-fresh behavior bypasses cache reads deterministically."
    - "maxAge freshness bounds are applied consistently for repeated equivalent fetch inputs."
  artifacts:
    - path: "src/sdk/contracts/fetch.ts"
      provides: "Fetch options contract with explicit cache policy controls"
    - path: "src/core/cache/fetch-cache.ts"
      provides: "Bounded cache utility implementing maxAge and fresh precedence semantics"
    - path: "src/tests/fetch-controls.integration.test.ts"
      provides: "REL-03 integration checks for cache hit/miss/bypass behavior"
    - path: "src/core/cache/fetch-cache.test.ts"
      provides: "Deterministic unit tests for cache precedence and staleness logic"
  key_links:
    - from: "src/sdk/fetch.ts"
      to: "src/core/policy/retrieval-controls.ts"
      via: "normalize fetch controls before cache lookup"
      pattern: "resolve(Fetch|Retrieval)Controls"
    - from: "src/sdk/fetch.ts"
      to: "src/core/cache/fetch-cache.ts"
      via: "read/write cache path around outbound fetch execution"
      pattern: "getCached|setCached|cache"
    - from: "src/core/cache/fetch-cache.ts"
      to: "src/sdk/contracts/fetch.ts"
      via: "cache key/value based on normalized fetch contract fields"
      pattern: "maxAge|fresh|cache"
---

<objective>
Implement fetch-path freshness and cost tuning controls through explicit cache policy semantics with deterministic precedence.

Purpose: Deliver REL-03 so callers can intentionally trade freshness for lower cost/latency without ambiguous cache behavior.
Output: Fetch contract/control updates, cache policy module, and unit/integration tests validating precedence and staleness behavior.
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
@.planning/phases/02-retrieval-controls-and-cost-tuning/02-RESEARCH.md
@.planning/phases/02-retrieval-controls-and-cost-tuning/02-01-SUMMARY.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add explicit fetch cache controls to contracts and SDK orchestration</name>
  <files>src/sdk/contracts/fetch.ts, src/sdk/fetch.ts</files>
  <action>Extend fetch input contracts with explicit cache policy options (for example `maxAgeMs` and `fresh`) while preserving existing response shape. Wire `fetch(...)` to consume normalized retrieval controls and apply clear precedence: `fresh=true` bypasses cache read; otherwise serve cache only if age is within maxAge policy. Keep semantics deterministic and documented in code comments where ambiguity is likely.</action>
  <verify>`npm run typecheck` passes and fetch entrypoint accepts new cache options without breaking existing call sites.</verify>
  <done>Fetch callers can pass cache controls and the sdk flow applies explicit precedence before outbound retrieval.</done>
</task>

<task type="auto">
  <name>Task 2: Implement bounded cache utility with deterministic precedence and keying</name>
  <files>src/core/cache/fetch-cache.ts, src/core/cache/fetch-cache.test.ts, src/sdk/fetch.ts</files>
  <action>Create a dedicated fetch cache utility (using established cache primitives already in project dependencies) that supports bounded storage, cache key normalization, maxAge checks, and force-fresh bypass behavior. Ensure keying is derived from normalized fetch inputs so equivalent inputs map to identical keys. Add unit tests covering hit, stale miss, forced bypass, and write-after-fetch behavior.</action>
  <verify>`npm run test -- src/core/cache/fetch-cache.test.ts` passes with deterministic cache precedence assertions.</verify>
  <done>Fetch cache behavior is deterministic, bounded, and reusable by fetch orchestration without inline cache logic duplication.</done>
</task>

<task type="auto">
  <name>Task 3: Add integration tests for REL-03 fetch freshness/cost behavior</name>
  <files>src/tests/fetch-controls.integration.test.ts</files>
  <action>Add integration tests for fetch cache semantics using deterministic fixtures/mocks: first call stores result, repeated call within maxAge reuses cache, stale entry triggers refresh, and `fresh=true` bypasses cache even when entry exists. Include one mixed-options test to verify precedence (`fresh` overrides read, but fresh response can still update cache for later non-fresh reads).</action>
  <verify>`npm run test -- src/tests/fetch-controls.integration.test.ts` passes.</verify>
  <done>REL-03 behavior is validated with automated tests proving fresh/maxAge precedence and repeatable outputs.</done>
</task>

</tasks>

<verification>
Run `npm run typecheck`, `npm run test -- src/core/cache/fetch-cache.test.ts`, and `npm run test -- src/tests/fetch-controls.integration.test.ts`.
</verification>

<success_criteria>
- Fetch callers can intentionally choose cache reuse vs fresh retrieval.
- Force-fresh and maxAge semantics are explicit, deterministic, and test-covered.
- Equivalent inputs follow stable cache keying and repeatable outcomes.
</success_criteria>

<output>
After completion, create `.planning/phases/02-retrieval-controls-and-cost-tuning/02-03-SUMMARY.md`
</output>
