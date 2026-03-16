---
phase: 02-retrieval-controls-and-cost-tuning
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/core/policy/retrieval-controls.ts
  - src/core/policy/retrieval-controls.test.ts
  - src/core/policy/domain-scope.ts
autonomous: true
must_haves:
  truths:
    - "A shared retrieval controls resolver exists with deterministic defaults and bounds."
    - "Out-of-range control values are clamped or rejected deterministically by policy normalization."
    - "Domain scope values are canonicalized consistently so include/exclude behavior is stable."
  artifacts:
    - path: "src/core/policy/retrieval-controls.ts"
      provides: "Single source of truth for defaults, bounds, and normalized control shapes"
    - path: "src/core/policy/domain-scope.ts"
      provides: "Canonical domain normalization and include/exclude policy helpers"
    - path: "src/core/policy/retrieval-controls.test.ts"
      provides: "Deterministic tests for defaults, bounds, and domain canonicalization"
  key_links:
    - from: "src/core/policy/retrieval-controls.ts"
      to: "src/core/policy/domain-scope.ts"
      via: "domain scope canonicalization helper"
      pattern: "normalizeDomain|normalizeDomainList"
    - from: "src/core/policy/retrieval-controls.test.ts"
      to: "src/core/policy/retrieval-controls.ts"
      via: "policy defaults and bounds coverage"
      pattern: "(maxResults|timeoutMs|fresh|country|language)"
---

<objective>
Create a shared retrieval controls foundation that both `search(...)` and `fetch(...)` consume, with strict defaults and deterministic option normalization.

Purpose: Prevent control drift between search and fetch by centralizing bounds, defaults, and scope semantics before wiring provider/cache behavior.
Output: Reusable control normalization and domain-scope policy modules with focused tests.
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
@.planning/phases/01-core-retrieval-engine/01-01-foundation-and-contracts-PLAN.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Build shared RetrievalControls resolver with strict defaults and bounds</name>
  <files>src/core/policy/retrieval-controls.ts</files>
  <action>Create a normalized controls module used by both public primitives. Implement explicit defaults and bounds for `maxResults`, `timeoutMs`, locale (`country=us`, `language=en`), freshness, and fetch cache knobs (`maxAgeMs`, `fresh`). Use zod parsing at this layer to enforce deterministic behavior and reject invalid combinations. Keep output provider-agnostic; do not expose Serper-specific payload fields from this module.</action>
  <verify>`npm run typecheck` passes and unit-level imports in both sdk entrypoints can consume the normalized control type without type errors.</verify>
  <done>A single `RetrievalControls` normalization source exists and can be reused across search and fetch flows.</done>
</task>

<task type="auto">
  <name>Task 2: Implement canonical domain scope normalization policy</name>
  <files>src/core/policy/domain-scope.ts, src/core/policy/retrieval-controls.ts</files>
  <action>Implement domain canonicalization helpers using `tldts` for include/exclude lists. Normalize input formats (scheme/no-scheme/subdomain), lower-case values, dedupe, and ensure conflict precedence is deterministic (exclude wins on overlap). Wire this into retrieval controls resolution so downstream query shaping and post-filtering consume canonical domain sets.</action>
  <verify>`npm run typecheck` passes and policy outputs for mixed domain inputs are deterministic in tests.</verify>
  <done>Search scope controls have a canonical domain policy representation suitable for both query-time and result-time enforcement.</done>
</task>

<task type="auto">
  <name>Task 3: Add focused policy tests for defaults, bounds, and scope canonicalization</name>
  <files>src/core/policy/retrieval-controls.test.ts</files>
  <action>Add tests that prove: (1) US + English defaults are always present when locale options are omitted, (2) maxResults and timeout bounds are enforced, (3) `fresh=true` semantics are represented explicitly in normalized controls, and (4) include/exclude domain normalization is stable and deduped. Keep tests fast and deterministic with no network calls.</action>
  <verify>`npm run test -- src/core/policy/retrieval-controls.test.ts` passes.</verify>
  <done>Policy behavior is executable-spec documented through tests and safe for dependent plans.</done>
</task>

</tasks>

<verification>
Run `npm run typecheck` and `npm run test -- src/core/policy/retrieval-controls.test.ts`.
</verification>

<success_criteria>
- Shared control resolution exists for both search and fetch paths.
- Defaults/bounds/locale/scope semantics are deterministic and test-covered.
- Domain policy output is canonicalized and ready for downstream enforcement.
</success_criteria>

<output>
After completion, create `.planning/phases/02-retrieval-controls-and-cost-tuning/02-01-SUMMARY.md`
</output>
