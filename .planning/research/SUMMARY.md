# Project Research Summary

**Project:** Web Search SDK
**Domain:** Cost-first web search + fetch SDK for agent applications
**Researched:** 2026-03-15
**Confidence:** MEDIUM-HIGH

## Executive Summary

This is an SDK-first retrieval product: a TypeScript package that exposes two stable primitives, `search(...)` and `fetch(...)`, where search is Serper-backed and fetch is handled by an in-house scraper. The strongest expert pattern is to keep the v1 API narrow and deterministic, then win on predictable cost, latency, and reliability instead of broad platform scope.

The recommended approach is contract-first and policy-first. Build canonical request/response contracts first, implement a Serper adapter for `search`, then ship an HTTP-first fetch pipeline with extraction quality gates, caching, and strict middleware for budgets, retries, and throttling. Architecture should preserve a transport seam from day one so local in-process execution can evolve into optional hosted execution without breaking SDK contracts.

The major risk is "cheap but wrong": optimizing for throughput/cost while relevance, compliance, and safety degrade silently. Mitigation is to ship quality and safety controls as first-class requirements: golden-query relevance regression, 429 discipline with retry budgets, robots/compliance policy engine, SSRF containment, canonicalization/dedup, and provenance metadata in every result path.

## Key Findings

### Recommended Stack

Research strongly supports a TypeScript/Node 24 LTS SDK stack with static-first scraping defaults and selective heavier fallbacks only when quality fails. The stack is intentionally optimized for low marginal cost per request, high control over retries/concurrency, and clean typed contracts.

**Core technologies:**
- `Node.js 24 LTS`: runtime baseline for production stability and modern fetch tooling.
- `TypeScript ^5.7`: strict public SDK contracts and safer integration ergonomics.
- `Serper API`: single-provider v1 search backend to reduce complexity and ship quickly.
- `undici ^7`: high-control HTTP transport for performance and connection tuning.
- `cheerio ^1.1`: low-overhead static HTML parsing for cost-first extraction.
- `zod ^4`, `p-retry`, `p-queue`: validation + bounded retry/backoff + concurrency/rate control.

### Expected Features

The feature set is clear: v1 should be reliable and economical, not broad. Users expect deterministic search/fetch, explicit controls for relevance and freshness, resilience on provider failure modes, and transparent per-call usage metadata.

**Must have (table stakes):**
- Stable normalized outputs for `search` and `fetch`.
- Cost/latency metadata on every response (`usage`, timing).
- Domain, locale, and recency controls with safe defaults.
- Retry/backoff with typed error taxonomy and bounded attempts.
- Fetch cache controls (`maxAge`, force-fresh) for explicit cost/speed tradeoffs.

**Should have (competitive):**
- Cost-aware modes (budget vs quality presets).
- Adaptive fetch strategy (HTTP-first, JS fallback on failure signals).
- Observability hooks (`onRequest`, `onRetry`, `onCost`).
- Lightweight optional extraction helpers for common post-processing.

**Defer (v2+):**
- Multi-provider routing/failover as productized capability.
- Crawl/map/research platform breadth.
- Browser-action workflow automation in core SDK.
- Default answer/summarization generation (keep opt-in only later).

### Architecture Approach

The architecture should center on a stable SDK facade, with policy-as-middleware, separate provider and scraper execution pipelines, and shared primitives for cache, throttling, telemetry, and circuit breaking. The recommended build order is: contracts first, then search slice, then HTTP fetch slice, then policy hardening, then browser fallback heuristics, and finally hosted transport seam and optional hosted planes.

**Major components:**
1. SDK facade: stable public API, validation, and normalized contracts.
2. Search adapter: isolates Serper-specific request/response behavior.
3. Fetch orchestrator + extraction pipeline: HTTP-first retrieval, quality scoring, controlled fallback.
4. Policy engine: budget checks, retries, timeout/concurrency/rate limits.
5. Cache + telemetry: dedupe spend, expose latency/cost/error signals.
6. Hosted seam (future): remote execution without contract changes.

### Critical Pitfalls

1. **Cost optimization before relevance controls** - enforce golden-query regression gates and citation coverage thresholds before performance wins are accepted.
2. **429/retry storms from weak rate control** - apply dual throttling (QPS + RPM), jittered backoff, `Retry-After` handling, and retry budgets.
3. **Robots/compliance as best-effort logic** - implement RFC-aware robots policy engine with cached host decisions and auditable allow/deny logs.
4. **Transport success treated as extraction success** - require extraction quality checks and confidence scoring before downstream use.
5. **Open `fetch` surface without SSRF containment** - enforce outbound policy, private/link-local/metadata blocking, and redirect revalidation.

## Implications for Roadmap

Based on combined findings, suggested phase structure:

### Phase 1: Contract + Secure Core Retrieval
**Rationale:** All later reliability and optimization work depends on stable contracts and safe baseline primitives.
**Delivers:** Typed `search`/`fetch` API, canonical output schema, URL canonicalization/dedup, SSRF-safe fetch boundary, base telemetry fields.
**Addresses:** v1 table-stakes primitives, cost visibility foundation.
**Avoids:** Pitfalls on dedup waste and open fetch attack surface.

### Phase 2: Reliability, Compliance, and Policy Hardening
**Rationale:** Production trust requires predictable failure behavior before advanced capability.
**Delivers:** Dual-limit throttling, retry budgets, circuit breakers, robots/compliance policy engine, provenance logging.
**Uses:** `p-retry`, `p-queue`, `robots-parser`, structured telemetry stack.
**Implements:** Policy-as-middleware and shared platform primitives.

### Phase 3: Relevance and Extraction Quality Gates
**Rationale:** Cost-first only works if quality remains acceptable and measurable.
**Delivers:** Golden-query evaluation harness, extraction confidence gates, challenge-page detection, relevance regression checks in CI.
**Addresses:** quality-focused table stakes and operational trust.
**Avoids:** silent relevance collapse and 200-but-useless extraction.

### Phase 4: Cost/Quality Differentiators
**Rationale:** Once baseline trust exists, add competitive levers that improve economics and developer UX.
**Delivers:** budget/quality presets, observability hooks, optional lightweight extraction helpers, bounded batch operations.
**Addresses:** differentiators from feature research.
**Avoids:** unbounded payload and hidden-spend anti-features.

### Phase 5: Adaptive Fetch and Hosted Evolution Seam
**Rationale:** Higher complexity should come after telemetry reveals where fallback and remote execution are actually needed.
**Delivers:** controlled browser fallback heuristics and transport seam (`local` vs `remote`) for hosted compatibility.
**Implements:** progressive fetch strategy and hosted adapter boundary.
**Avoids:** browser-first cost explosion and rewrite risk during future hosting.

### Phase 6 (Optional): Multi-provider and Hosted Planes
**Rationale:** Defer highest complexity until PMF and operational data justify expansion.
**Delivers:** provider resilience capabilities and optional control/data-plane services.
**Addresses:** deferred v2+ concerns.
**Avoids:** premature abstraction and infra overhead in v1.

### Phase Ordering Rationale

- Contracts and safety come first because every downstream phase depends on stable boundaries and secure fetch behavior.
- Reliability/compliance precede advanced capabilities to prevent expensive regressions and legal/security incidents.
- Quality gating lands before optimization features so cost wins do not degrade output usefulness.
- Hosted and multi-provider capabilities are intentionally deferred to avoid pre-PMF complexity.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 5:** adaptive fallback classifier thresholds and browser fallback economics need targeted experimentation.
- **Phase 6:** hosted control/data-plane design and multi-provider routing tradeoffs need scenario-specific architecture research.
- **Phase 3:** relevance/evaluation metric design may require domain-specific benchmark research for representative golden sets.

Phases with standard patterns (likely can skip research-phase):
- **Phase 1:** contract-first SDK + SSRF-safe URL policy is well-documented and straightforward.
- **Phase 2:** retry/throttle/circuit-breaker and robots policy patterns are mature with strong references.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Mostly anchored in official runtime/library docs and clear compatibility constraints. |
| Features | HIGH | Strong alignment across competitor docs and explicit v1/v2 boundary clarity. |
| Architecture | MEDIUM-HIGH | Design guidance is robust, but hosted-evolution details remain assumption-heavy until scale data exists. |
| Pitfalls | MEDIUM-HIGH | Risk patterns are well-supported by RFC/OWASP/Crawlee guidance; impact in this exact product still needs validation via tests. |

**Overall confidence:** MEDIUM-HIGH

### Gaps to Address

- **Serper operational variance:** limits/pricing/perf can shift; validate with load and budget tests before locking SLOs.
- **Adaptive fallback thresholds:** define with empirical quality/cost curves instead of static heuristics.
- **Relevance benchmark scope:** golden-query set must reflect actual target workflows before using as release gate.
- **Provenance/licensing policy details:** legal requirements for downstream usage should be reviewed before broader rollout.

## Sources

### Primary (HIGH confidence)
- [Node.js Releases](https://nodejs.org/en/about/previous-releases) - LTS posture and runtime baseline.
- [TypeScript documentation](https://www.typescriptlang.org/docs/) - version posture for SDK typing baseline.
- [Zod docs](https://zod.dev/) - TS compatibility for runtime schema validation.
- [RFC 9309 - Robots Exclusion Protocol](https://www.rfc-editor.org/rfc/rfc9309) - robots semantics and crawler policy behavior.
- [RFC 6585 - HTTP 429 Too Many Requests](https://www.rfc-editor.org/rfc/rfc6585) - rate-limit handling semantics.
- [OWASP SSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html) - outbound fetch threat controls.
- [Crawlee scaling docs](https://crawlee.dev/js/docs/guides/scaling-crawlers) - queue, throttling, and concurrency patterns.

### Secondary (MEDIUM confidence)
- [Serper](https://serper.dev/) - provider capabilities/pricing posture (marketing-level source).
- [Undici npm](https://www.npmjs.com/package/undici) - transport behavior and compatibility notes.
- [Cheerio npm](https://www.npmjs.com/package/cheerio) - static parsing approach for extraction.
- [Vitest docs](https://vitest.dev/) - testing ecosystem alignment for TypeScript SDK projects.
- [tsdown docs](https://tsdown.dev/) - bundling approach for modern package output.

### Tertiary (LOW confidence)
- Ecosystem trend observations on anti-bot failures and scraping reliability tradeoffs used for directional context.

---
*Research completed: 2026-03-15*
*Ready for roadmap: yes*
