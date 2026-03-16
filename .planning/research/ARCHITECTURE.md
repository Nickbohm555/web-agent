# Architecture Research

**Domain:** Search + scraping SDK tooling (Serper-backed search + in-house fetch)
**Researched:** 2026-03-15
**Confidence:** MEDIUM-HIGH

## Standard Architecture

### System Overview

```
┌───────────────────────────────────────────────────────────────────────────┐
│                           Consumer Application                            │
├───────────────────────────────────────────────────────────────────────────┤
│ Agent/Backend/Workflow code calls: sdk.search(...) and sdk.fetch(...)    │
└───────────────────────────────┬───────────────────────────────────────────┘
                                │
┌───────────────────────────────▼───────────────────────────────────────────┐
│                         TypeScript SDK Facade                             │
├───────────────────────────────────────────────────────────────────────────┤
│  API Surface   Cost Policy   Retry/Timeout Policy   Result Normalizer    │
│  (`search`)    (budget caps) (single strategy)      (stable contracts)    │
│  (`fetch`)                                                                │
└───────────────┬───────────────────────────────────────────────────────────┘
                │
┌───────────────▼───────────────────────────────────────────────────────────┐
│                           Execution Layer                                 │
├───────────────────────────────┬───────────────────────────────────────────┤
│ Search Pipeline               │ Fetch Pipeline                            │
│ - Serper adapter              │ - URL intake + robots check              │
│ - Query shaping               │ - HTTP first, browser fallback           │
│ - Search response mapping     │ - extraction + content normalization     │
└───────────────┬───────────────┴───────────────┬──────────────────────────┘
                │                               │
┌───────────────▼───────────────────────────────▼──────────────────────────┐
│                    Shared Platform Primitives                             │
├───────────────────────────────────────────────────────────────────────────┤
│ HTTP client │ bounded concurrency │ dedupe cache │ telemetry │ circuit    │
│             │ (per-domain/per-op) │ + TTL         │ + usage    │ breakers  │
└───────────────┬───────────────────────────────────────────────────────────┘
                │
┌───────────────▼───────────────────────────────────────────────────────────┐
│                    Optional Hosted Evolution Path                          │
├───────────────────────────────────────────────────────────────────────────┤
│ Control Plane: auth, quotas, routing policy, key management, analytics    │
│ Data Plane: search workers, fetch workers, queue, cache, extraction nodes │
└───────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| SDK facade | Stable public methods and option validation for `search` / `fetch` | TypeScript package with strict input/output schemas |
| Search adapter | Encapsulate Serper request/response details and retries | Provider module with one outbound integration |
| Fetch orchestrator | Decide crawl path (HTTP-only vs browser fallback) and enforce politeness | In-process orchestrator with domain-aware rate limits |
| Extraction pipeline | Convert raw HTML/DOM into clean text/metadata for agents | Parser chain (readability + sanitize + structure) |
| Cost policy engine | Enforce per-call and per-session cost budgets | Budget counters, operation weights, fail-fast checks |
| Cache + dedupe | Avoid repeated spend on identical queries/URLs | Memory/disk cache in SDK; Redis/object cache in hosted mode |
| Telemetry + metering | Track latency, spend, retries, and failure classes | Event emitters + optional hosted metrics sink |
| Optional control plane | Centralized config, auth, usage, and policy rollout | Lightweight API service (can be Go later) |
| Optional data plane | Run queue-backed workers for heavy scrape jobs | Worker pools with bounded concurrency and backpressure |

## Recommended Project Structure

```
src/
├── sdk/                          # Public package surface
│   ├── client/                   # SDK constructor, config, middleware
│   ├── tools/                    # search.ts, fetch.ts public methods
│   └── contracts/                # input/output types and validation
├── core/                         # Shared runtime primitives
│   ├── http/                     # retriable HTTP client + circuit breaker
│   ├── cache/                    # cache interfaces + implementations
│   ├── policy/                   # cost budget + concurrency policy
│   └── telemetry/                # metrics/events/log adapters
├── providers/
│   └── serper/                   # Serper-specific adapter and mapping
├── scraper/
│   ├── orchestrator/             # fetch pipeline decision logic
│   ├── workers/                  # HTTP worker, browser fallback worker
│   ├── extraction/               # parse/clean/chunk/metadata
│   └── robots/                   # robots.txt + crawl-delay checks
├── hosted/                       # Optional future hosted API path
│   ├── control-plane/            # auth/quotas/policy/config APIs
│   └── data-plane/               # queue consumers and job execution
└── tests/                        # contract, integration, and cost tests
```

### Structure Rationale

- **`sdk/` first:** keeps public API stable while internals evolve from local-only to hosted.
- **`core/` isolated:** shared policy/retry/cache logic avoids duplicated cost bugs across `search` and `fetch`.
- **`providers/` and `scraper/` split:** external dependency logic and in-house crawl logic change at different rates.
- **`hosted/` optional but pre-bounded:** enables later service extraction without breaking SDK contracts.

## Architectural Patterns

### Pattern 1: Policy-as-Middleware

**What:** Every tool call flows through budget, concurrency, retry, and timeout middleware before provider execution.
**When to use:** Always in v1; it is the cheapest way to keep cost predictable for startups.
**Trade-offs:** Slight latency overhead per call, but much lower runaway-spend risk.

**Example:**
```typescript
const client = createClient(config)
  .use(costBudgetMiddleware())
  .use(concurrencyMiddleware())
  .use(retryMiddleware());

const result = await client.search({ query: "ai tools", limit: 5 });
```

### Pattern 2: Progressive Fetch Strategy

**What:** Try low-cost HTTP extraction first, escalate to browser rendering only when needed.
**When to use:** Default fetch behavior for cost-first product strategy.
**Trade-offs:** Better cost profile, but adds orchestration complexity and fallback heuristics.

**Example:**
```typescript
const page = await fetchOrchestrator.run(url, {
  strategy: "http-first",
  fallback: "browser-on-failure-or-low-content",
});
```

### Pattern 3: Adapter Boundary for Hosted Evolution

**What:** Keep tool logic transport-agnostic so execution can run in-process (SDK mode) or remote (hosted mode).
**When to use:** From v1, even if hosted mode is not implemented yet.
**Trade-offs:** Slightly more abstraction early, but prevents SDK-breaking rewrites later.

## Data Flow

### Request Flow (`search`)

```
User Code
  ↓
sdk.search(query, options)
  ↓
Input validation + cost policy check
  ↓
Cache lookup (query/options key)
  ├─ hit  → normalize response → return
  └─ miss → Serper adapter → HTTP call to Serper
                    ↓
          map provider payload to SDK contract
                    ↓
              cache write + usage telemetry
                    ↓
                  return results
```

### Request Flow (`fetch`)

```
User Code
  ↓
sdk.fetch(url, options)
  ↓
URL validation + robots/politeness gate + budget check
  ↓
Cache lookup (canonical URL + extraction profile)
  ├─ hit  → return cached content
  └─ miss → HTTP fetch worker
              ├─ success and quality pass → extractor
              └─ fail/low-quality        → browser fallback worker → extractor
                                              ↓
                                   normalized content + metadata
                                              ↓
                                  cache write + telemetry + return
```

### Hosted Mode Data Flow (later)

```
SDK Tool Call
  ↓
Hosted gateway (auth, quota, routing)
  ↓
Queue/job submission (data plane)
  ↓
Search or fetch worker execution
  ↓
Result store/cache
  ↓
Synchronous response or async poll/stream
```

### Key Data Flows

1. **Spend-control flow:** request metadata -> policy engine -> allow/deny/shape -> execution.
2. **Result-normalization flow:** provider/scraper raw payload -> canonical schema -> stable SDK response.
3. **Learning loop flow:** latency + error + cost metrics -> policy tuning (timeouts, retries, fallback thresholds).

## Build Order and Dependencies

1. **Phase A: Contract-first SDK shell**
   - Build `search` and `fetch` method signatures, config schema, and normalized response contracts.
   - Dependency: none.
2. **Phase B: Search vertical slice**
   - Implement Serper adapter, query shaping, and response mapping with retries/timeouts.
   - Depends on: Phase A contracts.
3. **Phase C: Fetch vertical slice (HTTP-only)**
   - Implement URL validation, polite rate limiting, extraction, and basic caching.
   - Depends on: Phase A core primitives.
4. **Phase D: Cost-control and shared middleware hardening**
   - Add budget policy engine, circuit breakers, dedupe cache policy, telemetry.
   - Depends on: Phases B/C working baseline.
5. **Phase E: Browser fallback + quality heuristics**
   - Add escalation path only for low-quality or blocked pages.
   - Depends on: Phase C extraction quality scoring.
6. **Phase F: Hosted compatibility seam**
   - Introduce transport abstraction (`local` vs `remote`) while preserving SDK API.
   - Depends on: stable middleware and contracts.
7. **Phase G (optional): Hosted control/data plane**
   - Control plane for auth/quotas/config; data plane for queue-backed execution.
   - Depends on: Phase F seam and production telemetry.

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 0-1k users | In-process SDK execution, memory cache, conservative concurrency caps |
| 1k-100k users | Shared Redis/object cache, stronger per-domain throttling, remote execution toggle for heavy fetches |
| 100k+ users | Split control/data planes, queue-backed workers, regional routing, async job model for long fetch workloads |

### Scaling Priorities

1. **First bottleneck:** fetch concurrency and retry storms; fix with strict per-domain token buckets and capped retries.
2. **Second bottleneck:** duplicate spend on repeated queries/URLs; fix with canonicalization and multi-tier caching.

## Anti-Patterns

### Anti-Pattern 1: Provider leakage into public SDK contracts

**What people do:** Return Serper/raw scraper payloads directly.
**Why it's wrong:** Locks consumers to provider shape and makes hosted migration painful.
**Do this instead:** Always map to canonical `search`/`fetch` contracts and keep adapters internal.

### Anti-Pattern 2: Browser-first scraping by default

**What people do:** Render every page in a browser for simplicity.
**Why it's wrong:** Explodes cost and latency, especially at startup-scale budgets.
**Do this instead:** HTTP-first with explicit escalation criteria and per-domain fallback caps.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Serper API | Single provider adapter with strict timeout/retry budget | Provider quota and response variance should be isolated behind mapping layer |
| Target websites | Polite crawler access with robots and domain throttling | Domain-level backpressure is required to avoid bans and wasted retries |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `sdk/tools` <-> `core/policy` | Direct module call (middleware chain) | Keep policy decisions centralized and deterministic |
| `sdk/tools` <-> `providers/serper` | Adapter interface | Enables future provider replacement without contract breakage |
| `sdk/tools` <-> `scraper/orchestrator` | Orchestrator interface | Encapsulates HTTP-first/fallback strategy |
| `sdk` <-> `hosted/*` (future) | Transport adapter (HTTP/gRPC) | Same tool contract, different execution venue |

## Sources

- [Serper home/product details](https://serper.dev/) (official marketing + FAQ; MEDIUM confidence for performance/cost claims)
- [Crawlee Introduction](https://crawlee.dev/js/docs/introduction) (official docs; HIGH confidence for queue/retry/scaling capabilities)
- [Crawlee Scaling Guide](https://crawlee.dev/js/docs/guides/scaling-crawlers) (official docs; HIGH confidence for concurrency/backpressure patterns)
- [Crawlee README](https://raw.githubusercontent.com/apify/crawlee/master/README.md) (official repo; HIGH confidence for architectural feature set)

---
*Architecture research for: search + scraping SDK systems*
*Researched: 2026-03-15*
