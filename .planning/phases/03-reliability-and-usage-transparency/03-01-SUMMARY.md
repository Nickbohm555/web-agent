---
phase: 03
plan: 01
subsystem: reliability-and-usage-transparency
tags:
  - reliability
  - errors
  - retries
  - telemetry
  - metadata
requires:
  - Phase 01 normalized search and fetch primitives
  - Phase 02 retrieval controls and cache behavior
  - Shared transport boundaries for Serper and scraper calls
provides:
  - Canonical typed SDK error taxonomy with deterministic classification
  - Shared retry executor with Retry-After precedence and bounded budgets
  - Stable per-call metadata contract shared by search and fetch responses
affects:
  - src/core/errors/sdk-error.ts
  - src/core/errors/map-error.ts
  - src/core/reliability/retry-after.ts
  - src/core/reliability/execute-with-retry.ts
  - src/core/retry.ts
  - src/core/telemetry/call-meta.ts
  - src/sdk/contracts/search.ts
  - src/sdk/contracts/fetch.ts
  - src/providers/serper/client.ts
  - src/scraper/http-worker.ts
  - src/sdk/search.ts
  - src/sdk/fetch.ts
  - src/tests/core/reliability/execute-with-retry.test.ts
  - src/tests/core/telemetry/call-meta.test.ts
tech-stack:
  added: []
  patterns:
    - Centralize error classification before retry decisions
    - Honor Retry-After before deterministic fallback backoff
    - Build response metadata from monotonic timing utilities
key-files:
  created:
    - src/core/errors/sdk-error.ts
    - src/core/errors/map-error.ts
    - src/core/reliability/retry-after.ts
    - src/core/reliability/execute-with-retry.ts
    - src/core/telemetry/call-meta.ts
    - src/tests/core/telemetry/call-meta.test.ts
  modified:
    - src/core/retry.ts
    - src/providers/serper/client.ts
    - src/scraper/http-worker.ts
    - src/sdk/contracts/search.ts
    - src/sdk/contracts/fetch.ts
    - src/sdk/search.ts
    - src/sdk/fetch.ts
    - src/tests/core/reliability/execute-with-retry.test.ts
key-decisions:
  - Keep SDK failures on a stable discriminated union so callers branch on `kind` instead of provider-specific messages.
  - Route retryable outbound failures through one deterministic executor with explicit retry budgets and Retry-After precedence.
  - Require a shared `meta` object on search and fetch outputs so attempts, retries, cache behavior, and timings are inspectable without logs.
duration: unknown
completed: 2026-03-15
---

# Phase 03 Plan 01: Shared Reliability Contracts Summary

Completed the shared reliability foundation by locking typed error behavior, deterministic retries, and inspectable response metadata into reusable core modules consumed by both retrieval primitives.

## Outcome

Task commits `28fc0ab`, `54dd5be`, and `01c02c3` implemented the full plan scope in order.

- `28fc0ab` added [src/core/errors/sdk-error.ts](/Users/nickbohm/Desktop/tinkering/web-agent/src/core/errors/sdk-error.ts) and [src/core/errors/map-error.ts](/Users/nickbohm/Desktop/tinkering/web-agent/src/core/errors/map-error.ts), establishing the canonical SDK error taxonomy and deterministic classifier coverage in [src/tests/core/reliability/execute-with-retry.test.ts](/Users/nickbohm/Desktop/tinkering/web-agent/src/tests/core/reliability/execute-with-retry.test.ts).
- `54dd5be` added [src/core/reliability/retry-after.ts](/Users/nickbohm/Desktop/tinkering/web-agent/src/core/reliability/retry-after.ts) and [src/core/reliability/execute-with-retry.ts](/Users/nickbohm/Desktop/tinkering/web-agent/src/core/reliability/execute-with-retry.ts), then wired the shared retry path into [src/providers/serper/client.ts](/Users/nickbohm/Desktop/tinkering/web-agent/src/providers/serper/client.ts) and [src/scraper/http-worker.ts](/Users/nickbohm/Desktop/tinkering/web-agent/src/scraper/http-worker.ts).
- `01c02c3` added [src/core/telemetry/call-meta.ts](/Users/nickbohm/Desktop/tinkering/web-agent/src/core/telemetry/call-meta.ts), updated [src/sdk/contracts/search.ts](/Users/nickbohm/Desktop/tinkering/web-agent/src/sdk/contracts/search.ts) and [src/sdk/contracts/fetch.ts](/Users/nickbohm/Desktop/tinkering/web-agent/src/sdk/contracts/fetch.ts), and propagated stable per-call `meta` output through the search and fetch integrations with coverage in [src/tests/core/telemetry/call-meta.test.ts](/Users/nickbohm/Desktop/tinkering/web-agent/src/tests/core/telemetry/call-meta.test.ts).

The resulting baseline gives both SDK primitives one shared reliability contract: stable error kinds, predictable retry scheduling, and response metadata that can be inspected programmatically without exposing provider internals.

## Verification

- `npm install`
- `npm run typecheck`
- `npm run test`
- `npm run build`

Targeted checks from the plan were also satisfied through:

- `npm run test -- src/tests/core/reliability/execute-with-retry.test.ts src/tests/core/telemetry/call-meta.test.ts`

The delivered reliability slice now verifies:

- known transport and status failures map to stable SDK `kind` and `retryable` values
- retry counts and backoff remain deterministic for equivalent failure inputs
- valid `Retry-After` values override fallback delay calculations
- search and fetch results expose a stable `meta` object for duration, attempts, retries, cache state, and timings

## Deviations

The plan executed as written.

## Traceability

- `03-01-task1` -> `28fc0ab`
- `03-01-task2` -> `54dd5be`
- `03-01-task3` -> `01c02c3`
