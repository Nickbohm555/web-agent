---
phase: 04
plan: 01
subsystem: fetch-safety-and-compliance-guardrails
tags:
  - safety
  - compliance
  - fetch
  - url-policy
  - typed-errors
requires:
  - Phase 01 fetch HTTP-first orchestration
  - Phase 02 retrieval controls and fetch metadata contracts
  - Phase 03 typed SDK error and call metadata foundations
provides:
  - Shared typed safety and compliance decision contracts for fetch preflight stages
  - Deterministic URL preflight policy evaluation with explicit allow and deny outcomes
  - Typed public fetch safety errors that preserve machine-readable deny metadata
affects:
  - src/sdk/contracts/safety.ts
  - src/sdk/contracts/fetch.ts
  - src/core/policy/url-policy.ts
  - src/core/policy/safety-decision.ts
  - src/core/errors/fetch-safety-error.ts
  - src/tests/safety/url-policy.test.ts
  - src/sdk/index.ts
  - src/scraper/orchestrator.ts
tech-stack:
  added: []
  patterns:
    - Model fetch safety and compliance decisions as discriminated unions instead of stringly typed internal flags
    - Run fail-closed URL preflight evaluation before downstream fetch work is considered
    - Map policy denies into typed SDK-facing fetch errors that retain structured decision metadata
key-files:
  created:
    - src/sdk/contracts/safety.ts
    - src/core/policy/url-policy.ts
    - src/core/policy/safety-decision.ts
    - src/core/errors/fetch-safety-error.ts
    - src/tests/safety/url-policy.test.ts
  modified:
    - src/sdk/contracts/fetch.ts
    - src/sdk/index.ts
    - src/scraper/orchestrator.ts
    - src/tests/fetch/fetch.unit.test.ts
    - src/tests/fetch/fetch.stability.test.ts
    - src/tests/fetch/fetch.meta.test.ts
    - src/tests/fetch/fetch.reliability.test.ts
    - src/tests/fetch-controls.integration.test.ts
    - src/core/cache/fetch-cache.test.ts
key-decisions:
  - Keep safety and compliance contracts provider-agnostic so later SSRF and robots phases can reuse the same public decision surface.
  - Treat malformed URLs, unsafe schemes, inline credentials, and invalid hosts as explicit deny outcomes rather than thrown parsing failures.
  - Preserve the original deny reason and decision payload when surfacing public fetch safety errors so callers can branch without parsing message text.
duration: unknown
completed: 2026-03-15
---

# Phase 04 Plan 01: Safety Decision Contracts Summary

Completed the Phase 4 safety-contracts slice by introducing explicit fetch safety/compliance decision models, a deterministic URL preflight gate, and typed public policy-denied fetch errors.

## Outcome

Task commits `1da5e5f`, `4683a89`, and `9521cee` executed the plan in order.

- `1da5e5f` added `src/sdk/contracts/safety.ts`, extended `src/sdk/contracts/fetch.ts`, and wired the fetch surface to carry inspectable decision metadata needed for safety and compliance outcomes.
- `4683a89` added `src/core/policy/url-policy.ts` and `src/core/policy/safety-decision.ts`, establishing a fail-closed URL preflight evaluator with stable allow and deny decisions plus normalized target metadata.
- `9521cee` added `src/core/errors/fetch-safety-error.ts` and extended `src/tests/safety/url-policy.test.ts` so policy denies surface through typed SDK-facing fetch errors with unchanged machine-readable reason, stage, and target fields.

The resulting fetch preflight layer now satisfies the Phase 4 plan 04-01 intent: unsafe URL candidates are denied before outbound execution, and those denies are exposed through stable contracts rather than opaque runtime exceptions.

## Verification

- `npm install`
- `npm run typecheck`
- `npm run test`
- `npm run build`
- `npm run test -- src/tests/safety/url-policy.test.ts`

The targeted checks verify:

- shared safety/compliance contracts compile cleanly at the SDK boundary
- URL preflight decisions are deterministic for safe URLs, malformed inputs, unsupported schemes, inline credentials, and invalid hosts
- policy denies map to typed public fetch errors without mutating the underlying deny reason or decision metadata

## Deviations

The plan executed as written.

## Traceability

- `04-01-task1` -> `1da5e5f`
- `04-01-task2` -> `4683a89`
- `04-01-task3` -> `9521cee`
