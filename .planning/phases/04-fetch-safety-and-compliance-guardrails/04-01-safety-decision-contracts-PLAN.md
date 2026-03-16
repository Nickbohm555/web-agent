---
phase: 04-fetch-safety-and-compliance-guardrails
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/sdk/contracts/fetch.ts
  - src/sdk/contracts/safety.ts
  - src/core/policy/url-policy.ts
  - src/core/policy/safety-decision.ts
  - src/core/errors/fetch-safety-error.ts
  - src/tests/safety/url-policy.test.ts
autonomous: true
must_haves:
  truths:
    - "Fetch preflight makes an explicit safety decision before outbound execution."
    - "Unsafe URL inputs are denied with typed reasons instead of generic runtime errors."
    - "Developers can inspect machine-readable safety/compliance decision metadata from fetch flow."
  artifacts:
    - path: "src/sdk/contracts/safety.ts"
      provides: "Canonical typed safety/compliance decision contracts and reason enums"
    - path: "src/core/policy/url-policy.ts"
      provides: "Deterministic URL policy evaluation for scheme, credentials, host, and option constraints"
    - path: "src/core/errors/fetch-safety-error.ts"
      provides: "Typed policy-deny error surface for SDK callers"
    - path: "src/tests/safety/url-policy.test.ts"
      provides: "Unit coverage for allow/deny policy outcomes and reason determinism"
  key_links:
    - from: "src/core/policy/url-policy.ts"
      to: "src/sdk/contracts/safety.ts"
      via: "policy evaluator returns typed safety decisions"
      pattern: "SafetyDecision|SafetyDenyReason"
    - from: "src/sdk/fetch.ts"
      to: "src/core/policy/safety-decision.ts"
      via: "preflight policy check before fetch execution"
      pattern: "evaluateSafetyPreflight|runSafetyPreflight"
    - from: "src/core/errors/fetch-safety-error.ts"
      to: "src/sdk/contracts/safety.ts"
      via: "deny decision mapped to typed public error/outcome"
      pattern: "createFetchSafetyError|reason"
---

<objective>
Create the safety decision foundation for Phase 04 so all fetch safety/compliance behavior has one explicit, typed contract.

Purpose: Enforce fail-closed URL policy behavior and eliminate opaque policy failures before network I/O.
Output: Shared safety decision contracts, URL policy evaluator, and typed error mapping with unit tests.
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
@.planning/phases/04-fetch-safety-and-compliance-guardrails/04-RESEARCH.md
@.planning/phases/01-core-retrieval-engine/01-03-SUMMARY.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Define typed fetch safety/compliance decision contracts</name>
  <files>src/sdk/contracts/safety.ts, src/sdk/contracts/fetch.ts</files>
  <action>Create a dedicated safety contract module exporting discriminated unions/enums for `SafetyDecision` and `ComplianceDecision` with explicit reason codes (for example `UNSAFE_SCHEME`, `URL_HAS_CREDENTIALS`, `INVALID_HOST`, `SSRF_BLOCKED_IP`, `ROBOTS_DENY`, `ROBOTS_UNAVAILABLE`). Update fetch contracts to include inspectable decision metadata fields so callers can branch behavior without parsing ad hoc error text. Keep contracts provider-agnostic and stable.</action>
  <verify>`npm run typecheck` passes and contract imports compile in fetch modules.</verify>
  <done>Safety/compliance outcomes are represented by shared typed contracts and available to fetch orchestration.</done>
</task>

<task type="auto">
  <name>Task 2: Implement deterministic URL preflight policy evaluator</name>
  <files>src/core/policy/url-policy.ts, src/core/policy/safety-decision.ts</files>
  <action>Implement policy evaluation with WHATWG URL parsing and fail-closed deny behavior. Enforce allowed schemes (`http`, `https`), reject inline credentials, reject malformed/empty hosts, and normalize target metadata needed by downstream SSRF checks. Expose one orchestrator-facing function (`evaluateSafetyPreflight` or equivalent) that returns typed allow/deny decisions rather than throwing except for truly unexpected internal faults.</action>
  <verify>`npm run test -- src/tests/safety/url-policy.test.ts` passes for both allow and deny scenarios with deterministic reason codes.</verify>
  <done>Preflight URL policy can deterministically allow or deny any candidate URL before network execution.</done>
</task>

<task type="auto">
  <name>Task 3: Map policy-deny decisions to typed public fetch errors</name>
  <files>src/core/errors/fetch-safety-error.ts, src/tests/safety/url-policy.test.ts</files>
  <action>Create a typed safety error helper that converts deny decisions into stable SDK-facing error/outcome objects with machine-readable fields (reason code, stage, target host/url hints without leaking sensitive content). Extend tests to assert that deny reasons from policy evaluation surface unchanged through error mapping. Avoid generic `Error` text-only paths for policy rejects.</action>
  <verify>`npm run test -- src/tests/safety/url-policy.test.ts && npm run typecheck` both pass.</verify>
  <done>Policy denies are visible to developers through typed, inspectable outcomes instead of opaque exceptions.</done>
</task>

</tasks>

<verification>
Run `npm run typecheck` and `npm run test -- src/tests/safety/url-policy.test.ts` after implementing contracts and preflight policy logic.
</verification>

<success_criteria>
- URL safety decisions are computed before any outbound fetch attempt.
- Denied URLs return explicit typed reasons aligned to SAFE-01 expectations.
- Fetch safety/compliance metadata has a stable contract surface for downstream plans.
</success_criteria>

<output>
After completion, create `.planning/phases/04-fetch-safety-and-compliance-guardrails/04-01-SUMMARY.md`
</output>
