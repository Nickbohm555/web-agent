---
phase: 01-core-retrieval-engine
plan: 02
type: execute
wave: 2
depends_on: ["01-01"]
files_modified:
  - src/providers/serper/client.ts
  - src/providers/serper/mapper.ts
  - src/sdk/search.ts
  - src/tests/fixtures/serper/organic.json
  - src/tests/search/serper-mapper.test.ts
  - src/tests/search/search.integration.test.ts
autonomous: true
user_setup:
  - service: serper
    why: "Provider API access for live integration validation"
    env_vars:
      - name: SERPER_API_KEY
        source: "Serper dashboard API key page"
must_haves:
  truths:
    - "Calling `search(query, options)` returns normalized title/url/snippet fields with rank metadata."
    - "Search output shape stays provider-agnostic and stable for equivalent provider payloads."
    - "Search request behavior is bounded and predictable under transient provider failures."
  artifacts:
    - path: "src/providers/serper/client.ts"
      provides: "Serper HTTP transport with bounded retry and timeout behavior"
    - path: "src/providers/serper/mapper.ts"
      provides: "Deterministic Serper organic mapping into normalized search contract"
    - path: "src/sdk/search.ts"
      provides: "Public search orchestration and contract validation"
    - path: "src/tests/search/search.integration.test.ts"
      provides: "Search behavior tests for shape stability and retry-safe outcomes"
  key_links:
    - from: "src/sdk/search.ts"
      to: "src/providers/serper/client.ts"
      via: "provider call orchestration"
      pattern: "callSerper|serperClient"
    - from: "src/sdk/search.ts"
      to: "src/providers/serper/mapper.ts"
      via: "response mapping pipeline"
      pattern: "mapSerperOrganic"
    - from: "src/providers/serper/mapper.ts"
      to: "src/sdk/contracts/search.ts"
      via: "final output parse/validate"
      pattern: "SearchResult.*parse"
---

<objective>
Implement the complete Phase 01 search slice with Serper adapter boundaries and deterministic normalization behavior.

Purpose: Satisfy CORE-01 while preventing provider payload leakage and unstable rank/result shapes.
Output: Working `search(...)` path from SDK boundary through Serper adapter with deterministic mapping tests.
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
  <name>Task 1: Build Serper transport with bounded retry policy</name>
  <files>src/providers/serper/client.ts</files>
  <action>Implement Serper HTTP client using `undici` and the shared retry helper from `src/core/retry.ts`. Parse/validate provider response envelope at adapter boundary, apply explicit timeout, and classify retryable failures as network/429/5xx only. Keep raw provider payload internal to provider module; do not export provider-shaped types beyond adapter internals.</action>
  <verify>Run `npm run test -- src/tests/search/search.integration.test.ts` with mocked transport cases for 429/5xx retry and non-retryable 4xx abort behavior.</verify>
  <done>Serper client performs bounded retries deterministically and returns adapter-internal payload for mapping.</done>
</task>

<task type="auto">
  <name>Task 2: Implement deterministic Serper-to-contract mapping</name>
  <files>src/providers/serper/mapper.ts, src/tests/fixtures/serper/organic.json, src/tests/search/serper-mapper.test.ts</files>
  <action>Create mapping function from Serper `organic[]` results to normalized search contract. Canonicalize text fields (trim/defaults), ensure valid URL filtering, and derive deterministic rank metadata (`providerPosition` when present plus stable fallback index ordering). Add fixture-based tests to lock mapping behavior and prevent shape/rank drift across repeated runs for equivalent payloads.</action>
  <verify>`npm run test -- src/tests/search/serper-mapper.test.ts` passes and repeated fixture runs produce identical normalized arrays.</verify>
  <done>Equivalent provider payloads map to identical normalized contract outputs with stable rank metadata.</done>
</task>

<task type="auto">
  <name>Task 3: Wire SDK `search(...)` and integration tests</name>
  <files>src/sdk/search.ts, src/tests/search/search.integration.test.ts</files>
  <action>Replace placeholder search implementation with full orchestration: parse input contract, invoke Serper client, map payload, validate final output contract, and return normalized response shape. Ensure no provider-specific fields escape SDK boundary. Add integration-style tests that assert contract shape (`title`, `url`, `snippet`, rank metadata) and stable behavior for equivalent input/options combinations.</action>
  <verify>`npm run test -- src/tests/search/search.integration.test.ts` and `npm run typecheck` both pass.</verify>
  <done>`search(query, options)` satisfies CORE-01 with deterministic normalized outputs and provider payload isolation.</done>
</task>

</tasks>

<verification>
Run `npm run typecheck` and targeted search tests. If `SERPER_API_KEY` is available, also run one optional live smoke test variant and capture sanitized output shape only.
</verification>

<success_criteria>
- Public `search(...)` returns required normalized fields and rank metadata.
- Mapping logic is deterministic for equivalent payloads.
- Retry behavior is bounded and test-covered for transient failures.
</success_criteria>

<output>
After completion, create `.planning/phases/01-core-retrieval-engine/01-02-SUMMARY.md`
</output>
