---
phase: 02
plan: 02
subsystem: retrieval-controls-and-cost-tuning
tags:
  - search
  - serper
  - controls
  - domains
requires:
  - Phase 01 normalized search primitive
  - 02-01 shared retrieval controls policy
  - Serper adapter transport
provides:
  - Search SDK control normalization wired through the public entrypoint
  - Serper request shaping for maxResults, timeout, locale, freshness, and domain operators
  - Integration coverage for CTRL-01, CTRL-02, and CTRL-03 search behavior
affects:
  - src/sdk/contracts/search.ts
  - src/sdk/search.ts
  - src/providers/serper/client.ts
  - src/providers/serper/search-request.ts
  - src/providers/serper/search-result-filter.ts
  - src/tests/search-controls.integration.test.ts
tech-stack:
  added: []
  patterns:
    - Normalize controls once at the SDK boundary before provider execution
    - Keep Serper-specific mapping internal to adapter modules
    - Enforce domain scope both in query shaping and post-result filtering
key-files:
  created:
    - src/providers/serper/search-request.ts
    - src/providers/serper/search-result-filter.ts
    - src/tests/search-controls.integration.test.ts
  modified:
    - src/sdk/contracts/search.ts
    - src/sdk/search.ts
    - src/providers/serper/client.ts
key-decisions:
  - Reuse the shared retrieval-controls resolver as the only source of search defaults and bounds.
  - Express domain scope twice: query operators for recall shaping and post-filtering for deterministic enforcement.
  - Pin locale defaults to US and English and keep freshness mapping adapter-internal through Serper `tbs` values.
duration: unknown
completed: 2026-03-15
---

# Phase 02 Plan 02: Search Controls and Serper Mapping Summary

Delivered the search-side control plane so `search(...)` now accepts normalized latency, breadth, scope, locale, and freshness controls while keeping Serper request details internal.

## Outcome

Task commits `76e0c05`, `699c984`, and `4649aa3` implemented the full plan scope in order.

- `76e0c05` extended [`src/sdk/contracts/search.ts`](/Users/nickbohm/Desktop/Tinkering/web-agent/src/sdk/contracts/search.ts) and [`src/sdk/search.ts`](/Users/nickbohm/Desktop/Tinkering/web-agent/src/sdk/search.ts) so the search entrypoint resolves shared controls with deterministic defaults before provider execution.
- `699c984` added [`src/providers/serper/search-request.ts`](/Users/nickbohm/Desktop/Tinkering/web-agent/src/providers/serper/search-request.ts), [`src/providers/serper/search-result-filter.ts`](/Users/nickbohm/Desktop/Tinkering/web-agent/src/providers/serper/search-result-filter.ts), and the first version of [`src/tests/search-controls.integration.test.ts`](/Users/nickbohm/Desktop/Tinkering/web-agent/src/tests/search-controls.integration.test.ts) to map controls into Serper requests and enforce final URL scope.
- `4649aa3` completed the integration coverage and final search-path precedence behavior in [`src/sdk/search.ts`](/Users/nickbohm/Desktop/Tinkering/web-agent/src/sdk/search.ts) and [`src/tests/search-controls.integration.test.ts`](/Users/nickbohm/Desktop/Tinkering/web-agent/src/tests/search-controls.integration.test.ts).

## Verification

- `npm install`
- `npm run typecheck`
- `npm run test`
- `npm run build`

The resulting search path now enforces `maxResults`, timeout abort semantics, include/exclude domain scope, locale defaults, and stable freshness mapping with repeatable automated coverage.

## Deviations

The plan executed as written.

## Traceability

- `02-02-task1` -> `76e0c05`
- `02-02-task2` -> `699c984`
- `02-02-task3` -> `4649aa3`
