---
phase: 02
plan: 01
subsystem: retrieval-controls-and-cost-tuning
tags:
  - search
  - fetch
  - policy
  - controls
requires:
  - Phase 01 normalized search and fetch primitives
  - zod contract validation
  - tldts domain parsing
provides:
  - Shared retrieval controls normalization for search and fetch
  - Canonical include/exclude domain scope policy with exclude precedence
  - Executable policy tests for defaults, bounds, freshness, and scope stability
affects:
  - src/core/policy/retrieval-controls.ts
  - src/core/policy/domain-scope.ts
  - src/core/policy/retrieval-controls.test.ts
  - src/providers/serper/client.ts
  - src/sdk/contracts/search.ts
  - src/sdk/contracts/fetch.ts
  - src/sdk/search.ts
tech-stack:
  added: []
  patterns:
    - Normalize-then-execute retrieval controls
    - Canonical domain scope resolution before downstream enforcement
    - Fast deterministic policy tests without network calls
key-files:
  created:
    - src/core/policy/retrieval-controls.ts
    - src/core/policy/domain-scope.ts
    - src/core/policy/retrieval-controls.test.ts
  modified:
    - src/providers/serper/client.ts
    - src/sdk/contracts/search.ts
    - src/sdk/contracts/fetch.ts
    - src/sdk/search.ts
    - src/tests/setup.test.ts
key-decisions:
  - Centralize retrieval defaults and bounds in one provider-agnostic policy layer used by both primitives.
  - Pin locale defaults to US and English to prevent provider or environment drift.
  - Canonicalize domain scope with dedupe and exclude-wins precedence using registrable domains.
  - Represent fetch freshness explicitly with normalized `fresh` and `maxAgeMs` controls.
duration: unknown
completed: 2026-03-15
---

# Phase 02 Plan 01: Retrieval Controls Foundation Summary

Delivered a shared retrieval-control policy layer that normalizes defaults, clamps invalid input through schema validation, and stabilizes domain-scope behavior for both `search(...)` and `fetch(...)`.

## Outcome

Task commits `ed1d036`, `cfa7a2a`, and `50578c8` implemented the full plan scope in order.

- `ed1d036` created `src/core/policy/retrieval-controls.ts` and wired shared search/fetch control resolution into the SDK-facing contracts and search path.
- `cfa7a2a` added `src/core/policy/domain-scope.ts` and connected canonical include/exclude domain normalization into retrieval control resolution.
- `50578c8` added `src/core/policy/retrieval-controls.test.ts` to lock in deterministic defaults, bounds, freshness semantics, and exclude-precedence behavior.

## Verification

- `npm run typecheck`
- `npm run test -- src/core/policy/retrieval-controls.test.ts`

The resulting control layer now provides a single normalized source of truth for `maxResults`, `timeoutMs`, locale defaults, freshness, fetch cache knobs, and canonical domain policy output.

## Deviations

The plan executed as written.

## Traceability

- `02-01-task1` -> `ed1d036`
- `02-01-task2` -> `cfa7a2a`
- `02-01-task3` -> `50578c8`
