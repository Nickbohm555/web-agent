# Requirements

## v1 Requirements

### Core Retrieval
- [ ] **CORE-01**: User can call `search(query, options)` and receive normalized results with `title`, `url`, `snippet`, and rank metadata.
- [ ] **CORE-02**: User can call `fetch(url, options)` and receive clean page content (`text` and/or `markdown`) with consistent response structure.

### Retrieval Controls
- [ ] **CTRL-01**: User can control search cost and latency using `maxResults` and timeout options.
- [ ] **CTRL-02**: User can constrain search scope with `includeDomains` and `excludeDomains`.
- [ ] **CTRL-03**: User can tune relevance with locale/freshness controls, with US + English defaults.

### Reliability and Cost Transparency
- [ ] **REL-01**: User gets deterministic retry/backoff behavior for retryable errors (including rate-limit responses) with typed error outputs.
- [ ] **REL-02**: User can inspect per-call usage and timing metadata for both search and fetch operations.
- [ ] **REL-03**: User can control fetch freshness/cost tradeoffs with cache options (for example, `maxAge` and force-fresh behavior).

### Safety and Compliance
- [ ] **SAFE-01**: User is protected from unsafe outbound fetch behavior via URL and network safety policies (including SSRF guardrails).
- [ ] **SAFE-02**: User gets robots/compliance-aware fetch behavior with explicit allow/deny outcomes.

### Developer Experience
- [ ] **DX-01**: User integrates through a TypeScript SDK as the primary public developer surface.
- [ ] **DX-02**: User receives stable, documented TypeScript types for request options and response payloads.

## v2 Requirements (Deferred)

### Cost/Quality Differentiators
- [ ] **DIFF-01**: User can select preset retrieval modes (for example, budget mode and quality mode).
- [ ] **DIFF-02**: User gets adaptive fetch escalation (static-first with selective JS fallback on failure signals).
- [ ] **DIFF-03**: User can use optional observability hooks such as request, retry, and cost callbacks.

### Throughput and Convenience
- [ ] **THRU-01**: User can run bounded batch operations (`fetchMany` and/or `searchMany`).
- [ ] **THRU-02**: User can optionally request lightweight hybrid retrieval (search plus top-N content extracts) with strict cost caps.

### Architecture Evolution
- [ ] **ARCH-01**: User can keep the same SDK contracts when switching from local execution to an optional hosted backend.
- [ ] **ARCH-02**: User can optionally use a Go hosted service for tighter speed/cost control at scale.

## Out of Scope

- Multi-provider search in v1 (non-Serper providers) — delayed to keep v1 fast and cost-focused.
- Full crawl/map/research platform endpoints in v1 — outside the two-tool `search`/`fetch` scope.
- Browser-action automation flows in core v1 — too costly and operationally heavy for the initial wedge.
- Default built-in answer generation/summarization in v1 — retrieval primitives stay explicit and predictable.
- Enterprise RBAC/compliance platform features in v1 — not required for startup/internal validation milestone.
- Non-US/multilingual optimization in v1 — US + English focus first.

## Traceability

| Requirement ID | Phase | Status |
|----------------|-------|--------|
| CORE-01 | Phase 1 - SDK Foundation and Core Retrieval | Pending |
| CORE-02 | Phase 1 - SDK Foundation and Core Retrieval | Pending |
| CTRL-01 | Phase 2 - Retrieval Controls and Cost Tuning | Pending |
| CTRL-02 | Phase 2 - Retrieval Controls and Cost Tuning | Pending |
| CTRL-03 | Phase 2 - Retrieval Controls and Cost Tuning | Pending |
| REL-01 | Phase 3 - Reliability and Usage Transparency | Pending |
| REL-02 | Phase 3 - Reliability and Usage Transparency | Pending |
| REL-03 | Phase 2 - Retrieval Controls and Cost Tuning | Pending |
| SAFE-01 | Phase 4 - Fetch Safety and Compliance Guardrails | Pending |
| SAFE-02 | Phase 4 - Fetch Safety and Compliance Guardrails | Pending |
| DX-01 | Phase 1 - SDK Foundation and Core Retrieval | Pending |
| DX-02 | Phase 1 - SDK Foundation and Core Retrieval | Pending |

---
*Last updated: 2026-03-15 after requirements definition*
