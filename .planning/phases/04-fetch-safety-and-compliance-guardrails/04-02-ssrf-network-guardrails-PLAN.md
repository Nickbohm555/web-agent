---
phase: 04-fetch-safety-and-compliance-guardrails
plan: 02
type: execute
wave: 2
depends_on: ["04-01"]
files_modified:
  - src/core/network/ip-policy.ts
  - src/core/network/resolve-and-classify.ts
  - src/core/network/redirect-guard.ts
  - src/scraper/http-worker.ts
  - src/tests/safety/ssrf-guardrails.test.ts
autonomous: true
must_haves:
  truths:
    - "Fetch blocks private/internal/reserved network targets before retrieving page content."
    - "SSRF guardrail decisions include explicit deny reasons that application code can inspect."
    - "Redirect hops cannot bypass safety policy because each hop is revalidated."
  artifacts:
    - path: "src/core/network/ip-policy.ts"
      provides: "IP address classification and deny rules for SSRF-sensitive ranges"
    - path: "src/core/network/resolve-and-classify.ts"
      provides: "DNS resolution plus per-address safety decision engine"
    - path: "src/core/network/redirect-guard.ts"
      provides: "Redirect target validation helper enforcing per-hop safety checks"
    - path: "src/tests/safety/ssrf-guardrails.test.ts"
      provides: "Deterministic SSRF and redirect bypass prevention test coverage"
  key_links:
    - from: "src/core/network/resolve-and-classify.ts"
      to: "src/core/network/ip-policy.ts"
      via: "resolved addresses classified before allow decision"
      pattern: "lookup\\(|classifyIp|isDisallowed"
    - from: "src/scraper/http-worker.ts"
      to: "src/core/network/redirect-guard.ts"
      via: "redirect location validation before follow"
      pattern: "validateRedirectTarget|revalidateRedirect"
    - from: "src/core/network/resolve-and-classify.ts"
      to: "src/sdk/contracts/safety.ts"
      via: "network denies return typed safety reasons"
      pattern: "SSRF_BLOCKED_IP|SafetyDecision"
---

<objective>
Implement SSRF-safe network guardrails so fetch execution can only proceed to validated, policy-allowed network destinations.

Purpose: Prevent outbound fetch from reaching internal/private infrastructure and close redirect-based bypasses.
Output: DNS/IP classification safety layer, redirect revalidation guard, and SSRF-focused tests.
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
</context>

<tasks>

<task type="auto">
  <name>Task 1: Build IP classification policy for SSRF deny ranges</name>
  <files>src/core/network/ip-policy.ts</files>
  <action>Implement reusable IP safety classification helpers using `ipaddr.js` (and native `node:net` helpers where useful) to block loopback, private RFC1918, link-local, unique-local IPv6, multicast, and other reserved ranges relevant to SSRF prevention. Return typed deny reasons and preserve enough metadata for diagnostics (IP family/class), without exposing full sensitive internals.</action>
  <verify>`npm run test -- src/tests/safety/ssrf-guardrails.test.ts` includes passing classification cases for blocked and allowed public IP examples.</verify>
  <done>IP safety policy deterministically identifies disallowed SSRF target ranges with typed outcomes.</done>
</task>

<task type="auto">
  <name>Task 2: Implement DNS resolve-and-classify safety gate</name>
  <files>src/core/network/resolve-and-classify.ts</files>
  <action>Create resolver logic that performs DNS lookup (`all: true`) for target hostname, classifies every resolved address with `ip-policy`, and returns deny if any candidate violates safety policy. Handle resolver failures as explicit safety outcomes (not silent allow). Keep behavior deterministic for equivalent hostname + policy inputs.</action>
  <verify>`npm run test -- src/tests/safety/ssrf-guardrails.test.ts` passes cases for private-IP resolution denial, public-IP allow, and resolver-error outcome handling.</verify>
  <done>Network preflight can evaluate hostnames against SSRF policy before connection attempts.</done>
</task>

<task type="auto">
  <name>Task 3: Enforce redirect-hop revalidation in HTTP worker</name>
  <files>src/core/network/redirect-guard.ts, src/scraper/http-worker.ts, src/tests/safety/ssrf-guardrails.test.ts</files>
  <action>Update HTTP execution to avoid blind redirect following. Implement redirect guard helper that validates each `Location` target through the same URL + DNS/IP safety pipeline before follow. Cap redirect hops and return explicit deny outcomes for unsafe redirect destinations (`SSRF_REDIRECT_BLOCKED` or equivalent). Add tests for safe initial URL redirecting into blocked/private destination to prove bypass prevention.</action>
  <verify>`npm run test -- src/tests/safety/ssrf-guardrails.test.ts && npm run typecheck` both pass.</verify>
  <done>Redirect paths cannot bypass SSRF guardrails; every hop is policy-validated with explicit outcomes.</done>
</task>

</tasks>

<verification>
Run `npm run test -- src/tests/safety/ssrf-guardrails.test.ts`, then full `npm run typecheck` to confirm network safety modules integrate cleanly.
</verification>

<success_criteria>
- SSRF-sensitive address ranges are blocked before outbound content retrieval.
- DNS resolution and redirect revalidation both feed typed safety outcomes.
- Unsafe redirect targets are denied with explicit reason codes visible to callers.
</success_criteria>

<output>
After completion, create `.planning/phases/04-fetch-safety-and-compliance-guardrails/04-02-SUMMARY.md`
</output>
