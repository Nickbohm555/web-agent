---
phase: 02-retrieval-controls-and-cost-tuning
plan: 02
type: execute
wave: 2
depends_on:
  - "02-01"
files_modified:
  - src/sdk/contracts/search.ts
  - src/sdk/search.ts
  - src/providers/serper/search-request.ts
  - src/providers/serper/search-result-filter.ts
  - src/tests/search-controls.integration.test.ts
autonomous: true
must_haves:
  truths:
    - "A developer can cap search breadth and latency with maxResults and timeout controls."
    - "A developer can include or exclude domains with deterministic enforcement on final results."
    - "A developer gets stable US + English locale defaults and explicit freshness control behavior."
  artifacts:
    - path: "src/sdk/contracts/search.ts"
      provides: "Search options contract with control fields and default semantics"
    - path: "src/providers/serper/search-request.ts"
      provides: "Internal mapping from normalized controls to Serper request/query shape"
    - path: "src/providers/serper/search-result-filter.ts"
      provides: "Post-result domain policy enforcement for include/exclude constraints"
    - path: "src/tests/search-controls.integration.test.ts"
      provides: "End-to-end behavior checks for CTRL-01/CTRL-02/CTRL-03 search path"
  key_links:
    - from: "src/sdk/search.ts"
      to: "src/core/policy/retrieval-controls.ts"
      via: "normalize options before provider call"
      pattern: "resolve(Search|Retrieval)Controls"
    - from: "src/providers/serper/search-request.ts"
      to: "src/providers/serper/client.ts"
      via: "mapped request payload to transport call"
      pattern: "serper.*search|client.*search"
    - from: "src/providers/serper/search-result-filter.ts"
      to: "src/sdk/search.ts"
      via: "post-filter before SDK response normalization"
      pattern: "filter.*Domain|apply.*Domain"
---

<objective>
Implement search-path control behavior so callers can bound cost/latency, constrain domain scope, and tune locale/freshness while keeping provider details internal.

Purpose: Deliver CTRL-01, CTRL-02, and CTRL-03 for `search(...)` without leaking Serper-specific semantics into public SDK contracts.
Output: Updated search contracts + SDK orchestration + provider mapping/filter modules and integration tests.
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
  <name>Task 1: Extend search contracts and SDK flow for normalized control inputs</name>
  <files>src/sdk/contracts/search.ts, src/sdk/search.ts</files>
  <action>Add/normalize search control fields (`maxResults`, `timeoutMs`, `includeDomains`, `excludeDomains`, locale controls, freshness controls) at the SDK boundary. Ensure `search(...)` resolves controls via the shared policy module before any provider call, and enforce public provider-agnostic semantics in request and response shaping. Preserve backward compatibility for callers that omit new control fields by applying defaults deterministically.</action>
  <verify>`npm run typecheck` passes and existing search call signatures remain valid with optional control fields.</verify>
  <done>Search entrypoint accepts control options with deterministic defaults and uses normalized policy output.</done>
</task>

<task type="auto">
  <name>Task 2: Map controls to Serper request and enforce post-filtered domain scope</name>
  <files>src/providers/serper/search-request.ts, src/providers/serper/search-result-filter.ts, src/sdk/search.ts</files>
  <action>Create adapter-internal mapping from normalized controls to Serper request construction. Apply query shaping for include/exclude where useful, but enforce domain scope again after provider results are returned to guarantee CTRL-02. Ensure timeout control is applied using abort semantics in outbound provider requests. Keep all Serper-specific parameter details contained within provider modules; SDK contracts must remain provider-neutral.</action>
  <verify>`npm run test -- src/tests/search-controls.integration.test.ts` includes cases proving out-of-scope domains are removed and timeout/maxResults controls affect returned results deterministically.</verify>
  <done>Search control behavior is enforced both before and after provider calls, and provider leakage is contained to adapter files.</done>
</task>

<task type="auto">
  <name>Task 3: Add integration tests for CTRL-01/CTRL-02/CTRL-03 search behavior</name>
  <files>src/tests/search-controls.integration.test.ts</files>
  <action>Add integration-style tests (with deterministic fixtures/mocks) that verify: maxResults caps output size, timeout bounds provider call duration/failure behavior, include/exclude domain policies are enforced on final URLs, locale defaults to US+English when omitted, and freshness control mapping is stable. Include at least one mixed-options case to assert deterministic precedence.</action>
  <verify>`npm run test -- src/tests/search-controls.integration.test.ts` passes.</verify>
  <done>Search control requirements are validated via repeatable automated tests tied to roadmap success criteria.</done>
</task>

</tasks>

<verification>
Run `npm run typecheck` and `npm run test -- src/tests/search-controls.integration.test.ts`.
</verification>

<success_criteria>
- Search callers can bound results and timeout predictably.
- Domain include/exclude constraints are enforced on final normalized results.
- Locale/freshness behavior has deterministic defaults and tested mappings.
</success_criteria>

<output>
After completion, create `.planning/phases/02-retrieval-controls-and-cost-tuning/02-02-SUMMARY.md`
</output>
