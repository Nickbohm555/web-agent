# Roadmap

## Overview

This roadmap is derived directly from the v1 requirements and organizes delivery into coherent capability boundaries for core retrieval logic. It keeps `search` and `fetch` engine behavior central while sequencing controls, reliability, and safety so each phase produces testable outcomes. All v1 requirements are mapped exactly once.

**Depth:** comprehensive  
**Total v1 requirements:** 10  
**Coverage:** 10/10 mapped

## Phases

### Phase 1 - Core Retrieval Engine

**Goal:** Systems can execute normalized `search` and `fetch` operations through stable core logic.

**Dependencies:** None

**Requirements:**
- CORE-01
- CORE-02

**Success Criteria:**
1. A caller can execute `search(query, options)` and receive normalized results containing `title`, `url`, `snippet`, and rank metadata.
2. A caller can execute `fetch(url, options)` and receive clean content in a consistent response shape.
3. Core request/response behavior remains stable across repeated runs for equivalent inputs.

### Phase 2 - Retrieval Controls and Cost Tuning

**Goal:** Developers can control cost, latency, scope, and freshness tradeoffs during retrieval.

**Dependencies:** Phase 1

**Requirements:**
- CTRL-01
- CTRL-02
- CTRL-03
- REL-03

**Success Criteria:**
1. A developer can cap search breadth and latency using `maxResults` and timeout options.
2. A developer can restrict results to allowed domains and exclude unwanted domains.
3. A developer can apply locale/freshness controls while keeping US + English defaults.
4. A developer can use cache controls (for example `maxAge` and force-fresh behavior) to choose between freshness and lower cost.

### Phase 3 - Reliability and Usage Transparency

**Goal:** Developers can rely on predictable failure handling and inspect per-call operational metadata.

**Dependencies:** Phase 2

**Requirements:**
- REL-01
- REL-02

**Success Criteria:**
1. Retryable failures (including rate-limit responses) follow deterministic retry/backoff behavior with typed error outputs.
2. Non-retryable failures return stable, typed error categories that are actionable in application code.
3. Each `search` and `fetch` call exposes usage and timing metadata that developers can inspect programmatically.

### Phase 4 - Fetch Safety and Compliance Guardrails

**Goal:** Developers can use `fetch` with built-in network safety boundaries and robots-aware compliance outcomes.

**Dependencies:** Phase 1

**Requirements:**
- SAFE-01
- SAFE-02

**Success Criteria:**
1. Unsafe or disallowed target URLs are blocked by policy before outbound fetch execution.
2. Fetch behavior enforces network safety constraints (including SSRF guardrails) that are visible through explicit errors/outcomes.
3. Robots/compliance checks produce explicit allow/deny outcomes that developers can inspect before or during fetch execution.

## Progress

| Phase | Goal | Requirement Count | Status |
|------|------|-------------------|--------|
| 1 - Core Retrieval Engine | Execute normalized `search`/`fetch` core behavior | 2 | Pending |
| 2 - Retrieval Controls and Cost Tuning | Control retrieval scope, latency, and freshness | 4 | Pending |
| 3 - Reliability and Usage Transparency | Predictable failures and inspectable usage/timing | 2 | Pending |
| 4 - Fetch Safety and Compliance Guardrails | Safe, robots-aware fetch behavior | 2 | Pending |

---
*Last updated: 2026-03-15*
