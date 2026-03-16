# Feature Research

**Domain:** Cost-first web search + content fetch SDK for agent builders
**Researched:** 2026-03-15
**Confidence:** HIGH

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Deterministic `search(query, options)` with normalized results (`title`, `url`, `snippet`, rank) | Every agent stack needs stable web retrieval primitives, not provider-specific response shapes | LOW | Hide Serper response variance behind a strict TS type contract |
| Deterministic `fetch(url, options)` with clean content output (`markdown` and/or `text`) | Agent pipelines need full-page context, not just snippets | MEDIUM | Must handle extraction failures and return structured error codes |
| Query controls: `maxResults`, pagination cursor/offset, timeout | Baseline control of recall, latency, and cost | LOW | Keep options minimal in v1, avoid full provider parity surface |
| Domain controls (`includeDomains`, `excludeDomains`) | Common retrieval-quality requirement for startup RAG/agent workflows | LOW | Tavily/Brave both expose domain/ranking-style controls; users expect this class of filtering |
| Locale/freshness controls (country/language + recency window) | Teams need "latest + local" relevance for production agent behavior | MEDIUM | Map to provider-specific params; enforce clear defaults (`US`,`en`) |
| Built-in retry/backoff + rate-limit handling | Search/scrape APIs return 429/5xx in real workloads; SDK should handle basic resiliency | MEDIUM | Must include jitter and idempotent retry policy with sane max attempts |
| Cost visibility per call (`usage` in result metadata) | Cost is the primary pain; users need per-call economics visible by default | LOW | Return estimated or provider-reported credit usage alongside latency |
| Cache controls on `fetch` (`maxAge`, force-fresh) | Fetch providers expose cache/freshness knobs and major latency/cost tradeoffs | MEDIUM | Firecrawl-style cache semantics are now common; expose minimal but explicit policy |

### Differentiators (Competitive Advantage)

Features that set the product apart. Not required, but valuable.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Cost-aware defaults ("budget mode" and "quality mode") | Out-of-the-box cheaper behavior than Tavily-style advanced depth or expensive scrape defaults | MEDIUM | Core differentiation for "rival Tavily on speed/cost"; must be transparent and overridable |
| Single-call hybrid retrieval (`search` can optionally attach lightweight page extracts for top N) | Reduces orchestration overhead and improves speed for common agent tasks | HIGH | Must cap N and bytes aggressively to avoid hidden spend explosions |
| Adaptive fetch strategy (static-first, escalate to JS rendering only on failure signals) | Preserves success rate without always paying dynamic-render cost | HIGH | Requires failure classifier + fallback path; major cost/speed lever |
| First-class observability hooks (`onRequest`, `onRetry`, `onCost`) | Startup teams can debug quality and spend quickly in production | MEDIUM | Improves trust for internal production usage |
| Strict TS ergonomics (typed option presets + result discriminated unions) | Faster integration, fewer runtime mistakes, cleaner agent tool wrappers | LOW | Important for SDK-first adoption velocity |
| Optional structured extraction helpers (schema/prompt post-processing on fetched text) | Gives "enough extraction" without full crawl platform complexity | MEDIUM | Defer advanced schema orchestration to v1.x; keep v1 helper thin |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Multi-provider search abstraction in v1 | Teams want vendor redundancy immediately | Slows shipping, leaks provider edge-cases into API, increases testing matrix and maintenance cost | Ship Serper-only in v1 with a clean internal adapter boundary |
| Full crawl/map/research platform APIs in v1 | Competitors expose crawl/map/agentic research endpoints | Bloats surface beyond `search`/`fetch`, increases infra spend and reliability burden before PMF | Keep SDK to two primitives; add narrow batch fetch later if demand is proven |
| Browser-action scraping flows (click/type/wait/screenshot) in core v1 | Looks powerful for dynamic sites | Expensive, flaky, and operationally heavy; harms cost-first positioning | Start with static + selective JS fallback; publish escape hatches only |
| Auto-LLM answers/summaries included by default | Seems user-friendly and "complete" | Adds hidden token cost and quality ambiguity; undermines predictable economics | Return retrieval data only by default; add opt-in summarization later |
| Huge default payloads (raw HTML, images, metadata dumps) | Users ask for "all data just in case" | Major bandwidth/token waste, slower responses, unnecessary storage costs | Default to compact text/markdown + metadata essentials; add explicit expand flags |
| Real-time streaming/indexing guarantees in v1 | Feels like enterprise-grade feature | High complexity and ops burden not needed for internal trust milestone | Use documented freshness knobs + bounded staleness expectations |

## Feature Dependencies

```
[Normalized search/fetch response contracts]
    └──requires──> [Provider adapters (Serper + in-house scraper)]
                        └──requires──> [Error taxonomy + retry/backoff]

[Cost visibility metadata]
    └──requires──> [Usage accounting model per operation]

[Locale/freshness/domain controls]
    └──requires──> [Option mapping layer + validation]

[Adaptive fetch strategy]
    └──requires──> [Static fetch baseline]
                        └──requires──> [Failure classification]
                                            └──requires──> [Selective JS fallback path]

[Hybrid search+extract]
    └──enhances──> [Base search primitive]
    └──conflicts (cost predictability)──> [Unbounded default payloads]

[Auto-summaries by default]
    └──conflicts──> [Cost-first positioning]
```

### Dependency Notes

- **Normalized contracts require provider adapters:** the public SDK API stays stable while underlying provider params evolve.
- **Retry/backoff depends on error taxonomy:** without classified errors (retryable vs terminal), retries cause waste.
- **Cost visibility depends on usage accounting:** "cost-first" claims are not credible without per-call measurement.
- **Adaptive fetch requires static-first baseline:** selective escalation only works when a cheap default path exists.
- **Hybrid retrieval conflicts with unbounded payload defaults:** both together produce runaway cost/latency.

## MVP Definition

### Launch With (v1)

Minimum viable product — what's needed to validate the concept.

- [ ] Typed `search(query, options)` and `fetch(url, options)` with stable normalized outputs — core SDK promise.
- [ ] Cost/latency visibility in every response (`usage`, `timing`) — directly addresses primary user pain.
- [ ] Domain + locale + freshness controls (minimal set) — baseline production relevance controls.
- [ ] Retry/backoff + explicit error codes — required for trusted internal production usage.
- [ ] Fetch cache controls (`maxAge`, force fresh) — concrete cost/speed knob users can reason about.

### Add After Validation (v1.x)

Features to add once core is working.

- [ ] Batch operations (`fetchMany`, optional `searchMany`) — add when throughput and orchestration overhead become bottlenecks.
- [ ] Adaptive fetch fallback (JS only on failure signals) — add after baseline scraper telemetry is stable.
- [ ] Lightweight structured extraction helpers from fetched content — add when repeated extraction patterns emerge internally.
- [ ] Per-feature budget guards (e.g., max extracted bytes/pages per call) — add once real spend profiles are measured.

### Future Consideration (v2+)

Features to defer until product-market fit is established.

- [ ] Multi-provider failover/routing — defer until single-provider path is battle-tested and demand is clear.
- [ ] Crawl/map/research style endpoints — defer until SDK primitive PMF is proven.
- [ ] Browser-action workflow support — defer unless dynamic-site coverage is a proven blocker.
- [ ] Optional hosted optimization plane (Go service) — defer until client-only model hits latency or governance limits.

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Stable `search` + `fetch` contracts | HIGH | MEDIUM | P1 |
| Cost/latency visibility metadata | HIGH | LOW | P1 |
| Retry/backoff + typed errors | HIGH | MEDIUM | P1 |
| Domain/locale/freshness controls | HIGH | MEDIUM | P1 |
| Fetch cache policy controls | MEDIUM | MEDIUM | P1 |
| Batch operations | MEDIUM | MEDIUM | P2 |
| Adaptive fetch fallback | HIGH | HIGH | P2 |
| Structured extraction helpers | MEDIUM | MEDIUM | P2 |
| Multi-provider routing | MEDIUM | HIGH | P3 |
| Crawl/map/research endpoints | LOW (for current milestone) | HIGH | P3 |

**Priority key:**
- P1: Must have for launch
- P2: Should have, add when possible
- P3: Nice to have, future consideration

## Competitor Feature Analysis

| Feature | Competitor A (Tavily) | Competitor B (Firecrawl / Exa) | Our Approach |
|---------|------------------------|----------------------------------|--------------|
| Search depth/latency tiers | Multiple depth modes with different credit costs | Exa exposes latency profiles + deep mode | Start with explicit low-cost defaults; expose a small quality toggle only |
| Built-in content extraction | `include_raw_content` and separate extract endpoint | Firecrawl/Exa have rich content retrieval options | Keep fetch primitive focused on clean markdown/text with explicit cost controls |
| Advanced enrichment (answers/summaries/highlights) | Opt-in answer/research style features | Exa summaries/highlights; Firecrawl JSON extract | Make enrichment opt-in and post-MVP to preserve predictable spend |
| Crawl/map/platform breadth | Tavily has map/crawl/research endpoints | Firecrawl has crawl/map/actions | Deliberately do not mirror broad platform scope in v1 |
| Cost transparency controls | Credit model documented; usage can be returned | Firecrawl and Exa pricing/features expose per-operation tradeoffs | Treat per-call usage/timing metadata as first-class API output |

## Sources

- [Tavily Search API](https://docs.tavily.com/documentation/api-reference/endpoint/search) (official docs, accessed 2026-03-15)
- [Tavily Credits & Pricing](https://docs.tavily.com/documentation/api-credits) (official docs, accessed 2026-03-15)
- [Firecrawl Scrape Features](https://docs.firecrawl.dev/features/scrape) (official docs, accessed 2026-03-15)
- [Exa Contents Retrieval](https://docs.exa.ai/reference/contents-retrieval-with-exa-api) (official docs, accessed 2026-03-15)
- [Exa Pricing](https://exa.ai/pricing) (official pricing page, accessed 2026-03-15)
- [Brave Web Search API docs](https://api-dashboard.search.brave.com/app/documentation/web-search/query) (official docs, accessed 2026-03-15)
- [Serper homepage](https://serper.dev/) (official product page, accessed 2026-03-15; parameter-level docs not publicly discoverable from indexed pages)

---
*Feature research for: web search + scrape SDK (startup agent builders)*
*Researched: 2026-03-15*
