---
phase: 04
plan: 02
subsystem: fetch-safety-and-compliance-guardrails
tags:
  - safety
  - ssrf
  - network
  - redirects
  - fetch
requires:
  - Phase 04 plan 04-01 typed safety decision contracts
  - Phase 01 fetch worker and orchestration foundations
  - Phase 03 reliability metadata and retry infrastructure
provides:
  - Deterministic SSRF IP classification with typed deny reasons
  - DNS preflight resolution that fails closed on unsafe candidates or resolver failures
  - Redirect-hop safety revalidation so redirects cannot bypass network guardrails
affects:
  - src/core/network/ip-policy.ts
  - src/core/network/resolve-and-classify.ts
  - src/core/network/redirect-guard.ts
  - src/scraper/http-worker.ts
  - src/sdk/contracts/safety.ts
  - src/tests/safety/ssrf-guardrails.test.ts
  - package.json
  - package-lock.json
tech-stack:
  added:
    - ipaddr.js
  patterns:
    - Classify resolved IPv4 and IPv6 candidates before any outbound fetch attempt
    - Deny hostnames when any resolved address is unsafe or DNS resolution fails
    - Disable blind redirect trust by revalidating each redirect target with the same safety pipeline
key-files:
  created:
    - src/core/network/ip-policy.ts
    - src/core/network/resolve-and-classify.ts
    - src/core/network/redirect-guard.ts
  modified:
    - src/scraper/http-worker.ts
    - src/sdk/contracts/safety.ts
    - src/tests/safety/ssrf-guardrails.test.ts
    - package.json
    - package-lock.json
key-decisions:
  - Treat SSRF-sensitive IP ranges as explicit typed deny outcomes instead of transport failures.
  - Fail closed when DNS resolution errors prevent safe host classification.
  - Reuse the same preflight safety model for redirect targets so a safe initial URL cannot pivot into private infrastructure.
duration: unknown
completed: 2026-03-15
---

# Phase 04 Plan 02: SSRF Network Guardrails Summary

Completed the Phase 4 SSRF guardrail slice by adding IP classification, DNS resolve-and-classify preflight, and redirect-hop revalidation to the fetch path.

## Outcome

Task commits `b1c5f3c`, `d4d2a9d`, and `d029677` executed the plan in order.

- `b1c5f3c` added [src/core/network/ip-policy.ts](/Users/nickbohm/Desktop/Tinkering/web-agent/src/core/network/ip-policy.ts) and [src/tests/safety/ssrf-guardrails.test.ts](/Users/nickbohm/Desktop/Tinkering/web-agent/src/tests/safety/ssrf-guardrails.test.ts), establishing deterministic classification for blocked private/internal/reserved targets and public allow cases.
- `d4d2a9d` added [src/core/network/resolve-and-classify.ts](/Users/nickbohm/Desktop/Tinkering/web-agent/src/core/network/resolve-and-classify.ts) and updated [src/sdk/contracts/safety.ts](/Users/nickbohm/Desktop/Tinkering/web-agent/src/sdk/contracts/safety.ts) plus [src/tests/safety/ssrf-guardrails.test.ts](/Users/nickbohm/Desktop/Tinkering/web-agent/src/tests/safety/ssrf-guardrails.test.ts), so hostname preflight resolves all candidates, denies any unsafe result, and returns explicit outcomes for resolver failures.
- `d029677` added [src/core/network/redirect-guard.ts](/Users/nickbohm/Desktop/Tinkering/web-agent/src/core/network/redirect-guard.ts) and updated [src/scraper/http-worker.ts](/Users/nickbohm/Desktop/Tinkering/web-agent/src/scraper/http-worker.ts) plus [src/tests/safety/ssrf-guardrails.test.ts](/Users/nickbohm/Desktop/Tinkering/web-agent/src/tests/safety/ssrf-guardrails.test.ts), enforcing per-hop redirect validation with explicit unsafe-redirect denial behavior.

The fetch pipeline now blocks disallowed network destinations before content retrieval and prevents redirect-based SSRF bypasses with inspectable, typed safety outcomes.

## Verification

- `npm install`
- `npm run typecheck`
- `npm run test`
- `npm run build`
- `npm run test -- src/tests/safety/ssrf-guardrails.test.ts`

The targeted SSRF suite verifies:

- blocked and allowed IP classifications remain deterministic
- DNS preflight denies private/reserved resolution candidates and handles resolver failures explicitly
- redirects into unsafe destinations are denied before downstream retrieval continues

## Deviations

The plan executed as written.

## Traceability

- `04-02-task1` -> `b1c5f3c`
- `04-02-task2` -> `d4d2a9d`
- `04-02-task3` -> `d029677`
