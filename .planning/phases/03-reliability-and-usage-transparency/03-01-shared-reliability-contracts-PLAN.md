---
phase: 03-reliability-and-usage-transparency
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/core/errors/sdk-error.ts
  - src/core/errors/map-error.ts
  - src/core/reliability/retry-after.ts
  - src/core/reliability/execute-with-retry.ts
  - src/core/telemetry/call-meta.ts
  - src/sdk/contracts/search.ts
  - src/sdk/contracts/fetch.ts
  - src/tests/core/reliability/execute-with-retry.test.ts
  - src/tests/core/telemetry/call-meta.test.ts
autonomous: true
must_haves:
  truths:
    - "Retryable failures are classified deterministically and use stable retry scheduling rules."
    - "Rate-limit responses honor `Retry-After` before fallback backoff."
    - "SDK errors expose stable typed categories with explicit retryability."
    - "Search/fetch contracts define per-call metadata fields with predictable shape."
  artifacts:
    - path: "src/core/errors/sdk-error.ts"
      provides: "Canonical discriminated-union error contract with stable `kind` and `retryable` fields"
    - path: "src/core/reliability/execute-with-retry.ts"
      provides: "Shared deterministic retry executor with bounded retry budget"
    - path: "src/core/reliability/retry-after.ts"
      provides: "Retry-After parser supporting delay-seconds and HTTP-date"
    - path: "src/core/telemetry/call-meta.ts"
      provides: "Monotonic timing and usage metadata builder for operation calls"
    - path: "src/sdk/contracts/search.ts"
      provides: "Search response schema updated with stable per-call meta"
    - path: "src/sdk/contracts/fetch.ts"
      provides: "Fetch response schema updated with stable per-call meta"
  key_links:
    - from: "src/core/reliability/execute-with-retry.ts"
      to: "src/core/errors/map-error.ts"
      via: "error classification determines retry decision path"
      pattern: "classify|map.*Error"
    - from: "src/core/reliability/execute-with-retry.ts"
      to: "src/core/reliability/retry-after.ts"
      via: "429 retry delay selection"
      pattern: "parseRetryAfter"
    - from: "src/sdk/contracts/search.ts"
      to: "src/core/telemetry/call-meta.ts"
      via: "response contract includes generated call meta shape"
      pattern: "meta"
---

<objective>
Create the shared reliability and metadata contract foundation consumed by both `search(...)` and `fetch(...)`.

Purpose: Prevent reliability drift by centralizing typed error mapping, deterministic retries, and response metadata schema before method-specific wiring.
Output: Canonical SDK error taxonomy, deterministic retry executor, Retry-After parsing, metadata builder, and updated search/fetch contracts.
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
@.planning/phases/01-core-retrieval-engine/01-01-foundation-and-contracts-PLAN.md
@.planning/phases/02-retrieval-controls-and-cost-tuning/02-01-retrieval-controls-foundation-PLAN.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Define canonical typed SDK errors and deterministic classifier</name>
  <files>src/core/errors/sdk-error.ts, src/core/errors/map-error.ts</files>
  <action>Create discriminated-union SDK error types with stable `kind`, `retryable`, `message`, optional `statusCode`, and optional `retryAfterMs`. Include at minimum: `rate_limited`, `timeout`, `network`, `provider_unavailable`, `invalid_request`, `policy_denied`, `content_unavailable`, and `unknown`. Implement one mapper/classifier that converts transport/provider/internal failures into these categories using explicit status/error-code mapping (do not branch on freeform message text). Keep provider payload internals out of exported error shapes.</action>
  <verify>`npm run typecheck` passes and `src/tests/core/reliability/execute-with-retry.test.ts` includes assertions that known failure inputs map to stable `kind` values and retryability flags.</verify>
  <done>Error outputs are actionable in app code through stable discriminants and deterministic mapping rules.</done>
</task>

<task type="auto">
  <name>Task 2: Implement shared deterministic retry executor with Retry-After precedence</name>
  <files>src/core/reliability/retry-after.ts, src/core/reliability/execute-with-retry.ts, src/tests/core/reliability/execute-with-retry.test.ts</files>
  <action>Implement a reusable reliability wrapper using `p-retry` with deterministic defaults (`randomize: false`) and explicit retry budgets (`retries`, `minTimeout`, `maxTimeout`, `maxRetryTime`). Parse `Retry-After` (both seconds and HTTP-date) for `429` and transient overload responses; when a valid value exists, use it before fallback deterministic backoff. Ensure non-retryable errors abort immediately via typed SDK error mapping. Add focused tests for retry count determinism, Retry-After precedence, non-retryable short-circuiting, and budget exhaustion behavior.</action>
  <verify>`npm run test -- src/tests/core/reliability/execute-with-retry.test.ts` passes with deterministic attempt/retry assertions.</verify>
  <done>Search/fetch can call one shared retry path that is deterministic and standards-aligned for rate-limit handling.</done>
</task>

<task type="auto">
  <name>Task 3: Add shared per-call metadata builder and wire contract meta fields</name>
  <files>src/core/telemetry/call-meta.ts, src/sdk/contracts/search.ts, src/sdk/contracts/fetch.ts, src/tests/core/telemetry/call-meta.test.ts</files>
  <action>Create metadata builder utilities using monotonic timing (`performance.now()`) with a stable output shape usable by both methods. Required fields: `operation`, `durationMs`, `attempts`, `retries`, `cacheHit`, and `timings` object for phase-level durations; include optional namespaced usage details (for provider/cache counters) without leaking raw provider payloads. Update search/fetch response schemas to require/accept this `meta` object and add schema/shape tests. Do not include raw request bodies, API keys, or full provider responses in metadata.</action>
  <verify>`npm run test -- src/tests/core/telemetry/call-meta.test.ts && npm run typecheck` both pass.</verify>
  <done>REL-02 metadata contract baseline exists for both primitives and can be populated consistently in integration plans.</done>
</task>

</tasks>

<verification>
Run `npm run typecheck` and `npm run test -- src/tests/core/reliability/execute-with-retry.test.ts src/tests/core/telemetry/call-meta.test.ts`.
</verification>

<success_criteria>
- Shared retry/error/meta modules exist and are reusable by both operations.
- Retry behavior is deterministic with explicit Retry-After precedence.
- Search/fetch public contracts include stable per-call metadata fields.
</success_criteria>

<output>
After completion, create `.planning/phases/03-reliability-and-usage-transparency/03-01-SUMMARY.md`
</output>
