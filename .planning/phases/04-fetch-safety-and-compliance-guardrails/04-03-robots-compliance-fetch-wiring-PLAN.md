---
phase: 04-fetch-safety-and-compliance-guardrails
plan: 03
type: execute
wave: 3
depends_on: ["04-01", "04-02"]
files_modified:
  - src/scraper/robots/client.ts
  - src/scraper/robots/evaluator.ts
  - src/scraper/orchestrator.ts
  - src/sdk/fetch.ts
  - src/tests/fixtures/robots/allow-all.txt
  - src/tests/fixtures/robots/deny-path.txt
  - src/tests/fetch/fetch.safety-compliance.integration.test.ts
autonomous: true
must_haves:
  truths:
    - "Robots/compliance checks return explicit allow/deny/unknown/unavailable outcomes."
    - "Fetch execution order is safety preflight -> robots/compliance -> HTTP retrieval, with deny outcomes short-circuiting execution."
    - "Developers can inspect whether a fetch was blocked by robots/compliance versus network safety policy."
  artifacts:
    - path: "src/scraper/robots/evaluator.ts"
      provides: "RFC-aware robots decision evaluation and typed compliance outcomes"
    - path: "src/scraper/orchestrator.ts"
      provides: "Fetch pipeline wiring that enforces policy/compliance gates before HTTP body fetch"
    - path: "src/sdk/fetch.ts"
      provides: "Public fetch outcome surface exposing policy/compliance decisions"
    - path: "src/tests/fetch/fetch.safety-compliance.integration.test.ts"
      provides: "End-to-end verification of allow/deny outcomes and stage-specific failures"
  key_links:
    - from: "src/scraper/orchestrator.ts"
      to: "src/core/policy/safety-decision.ts"
      via: "preflight safety gate before robots and HTTP stages"
      pattern: "evaluateSafetyPreflight|SafetyDecision"
    - from: "src/scraper/orchestrator.ts"
      to: "src/scraper/robots/evaluator.ts"
      via: "robots decision stage before content fetch"
      pattern: "evaluateRobotsCompliance|ComplianceDecision"
    - from: "src/sdk/fetch.ts"
      to: "src/scraper/orchestrator.ts"
      via: "final fetch response/error mapping with decision metadata"
      pattern: "orchestrateFetch|complianceDecision|safetyDecision"
---

<objective>
Complete Phase 04 by wiring robots/compliance evaluation into fetch orchestration with explicit, inspectable allow/deny outcomes.

Purpose: Satisfy SAFE-02 and finish SAFE-01 visibility by ensuring fetch never performs hidden compliance decisions.
Output: Robots evaluator/client, safety-compliance-aware fetch orchestration, and integration tests proving explicit outcomes.
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
@.planning/phases/04-fetch-safety-and-compliance-guardrails/04-01-SUMMARY.md
@.planning/phases/04-fetch-safety-and-compliance-guardrails/04-02-SUMMARY.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Implement robots retrieval and compliance evaluator</name>
  <files>src/scraper/robots/client.ts, src/scraper/robots/evaluator.ts, src/tests/fixtures/robots/allow-all.txt, src/tests/fixtures/robots/deny-path.txt</files>
  <action>Create robots client/evaluator modules that fetch and parse `robots.txt` using `robots-parser`, evaluate target URL against configured user-agent token, and return explicit compliance outcomes (`ALLOW`, `DENY`, `UNKNOWN`, `UNAVAILABLE`) with reason metadata. Implement fail-closed default for unreachable robots in safety mode, while structuring evaluator options so future policy override can be added without refactor.</action>
  <verify>`npm run test -- src/tests/fetch/fetch.safety-compliance.integration.test.ts` includes passing robots allow/deny/unavailable outcome assertions.</verify>
  <done>Robots compliance stage exists as a first-class typed decision engine with explicit outcomes.</done>
</task>

<task type="auto">
  <name>Task 2: Wire orchestrator and SDK fetch to staged safety/compliance pipeline</name>
  <files>src/scraper/orchestrator.ts, src/sdk/fetch.ts</files>
  <action>Update fetch orchestration order to enforce: URL/network safety preflight (from Plan 01/02) -> robots compliance evaluation -> HTTP worker/content extraction. Short-circuit on any deny outcome and return stage-specific typed results/errors so callers can distinguish safety policy blocks from robots blocks and transport failures. Keep HTTP-first behavior and do not introduce browser-first defaults.</action>
  <verify>`npm run test -- src/tests/fetch/fetch.safety-compliance.integration.test.ts` passes scenario matrix covering URL deny, SSRF deny, robots deny, robots unavailable, and allowed fetch.</verify>
  <done>Public `fetch(...)` behavior exposes explicit safety/compliance outcomes and enforces preflight gating before network retrieval.</done>
</task>

<task type="auto">
  <name>Task 3: Add end-to-end integration coverage for SAFE-01 and SAFE-02</name>
  <files>src/tests/fetch/fetch.safety-compliance.integration.test.ts</files>
  <action>Create integration tests that validate phase success criteria directly: blocked unsafe URL before outbound execution, visible SSRF guardrail outcomes, and inspectable robots allow/deny states. Assert stable contract fields for outcomes and reason codes, and include at least one test proving denied states do not call downstream HTTP fetch worker.</action>
  <verify>`npm run test -- src/tests/fetch/fetch.safety-compliance.integration.test.ts && npm run typecheck && npm run build` all pass.</verify>
  <done>SAFE-01 and SAFE-02 are objectively verified through executable tests tied to typed fetch outcomes.</done>
</task>

</tasks>

<verification>
Run end-of-plan gate: `npm run typecheck`, `npm run test`, and `npm run build`.
</verification>

<success_criteria>
- Robots evaluation returns explicit allow/deny/unknown/unavailable outcomes.
- Fetch executes only after safety and compliance gates allow execution.
- Developers can inspect and distinguish URL/network safety blocks from robots/compliance blocks.
</success_criteria>

<output>
After completion, create `.planning/phases/04-fetch-safety-and-compliance-guardrails/04-03-SUMMARY.md`
</output>
