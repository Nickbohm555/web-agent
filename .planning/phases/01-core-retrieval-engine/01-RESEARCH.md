# Phase 01: Core Retrieval Engine - Research

**Researched:** 2026-03-15  
**Domain:** TypeScript retrieval core (`search` + `fetch`) with Serper provider and HTTP-first content extraction  
**Confidence:** MEDIUM

## Summary

Phase 01 should be planned around a strict boundary: provider-specific behavior stays internal, while public outputs are normalized and stable. For `search`, Serper remains the only v1 provider, and the response mapping should canonicalize the provider payload into a fixed contract (`title`, `url`, `snippet`, rank metadata) with deterministic ordering. For `fetch`, the standard approach is an HTTP-first pipeline that gates requests with `robots.txt`, parses/extracts content from HTML, and only falls back to browser automation for explicit failure/quality reasons.

The ecosystem for this phase is stable and well-supported: `undici` for HTTP, `zod` for runtime contracts, `p-retry` and `p-queue` for resilience and rate control, `robots-parser` and `tldts` for URL/domain and politeness logic, and `@mozilla/readability` + `turndown` + `cheerio` for extraction and normalization. These libraries are mainstream and avoid hand-rolled edge-case code.

For planning quality, treat stability as a first-class requirement: canonicalize inputs, enforce bounded retries/timeouts, include explicit fallback reasons, and pin response shapes in tests. This phase should deliver predictable behavior across repeated equivalent inputs, not just functional happy-path output.

**Primary recommendation:** Build a contract-first retrieval pipeline with strict `zod` input/output validation and deterministic normalization at every boundary (`search` mapping, URL canonicalization, extracted content formatting).

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `undici` | `7.24.3` | HTTP client for provider calls and page fetches | High-performance Node HTTP client with modern fetch/request support |
| `zod` | `4.3.6` | Runtime validation and normalized contracts | Single source of truth for request/response schemas |
| `p-retry` | `7.1.1` | Bounded retries/backoff for transient failures | Explicit retry policies and abort semantics |
| `p-queue` | `9.1.0` | Concurrency and interval rate limiting | Prevents burst traffic and runaway parallelism |
| `pino` | `10.3.1` | Structured observability logs | Fast JSON logging with production-grade ecosystem |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `robots-parser` | `3.0.1` | Parse robots directives and crawl delay | Before every outbound `fetch` to evaluate allow/disallow |
| `tldts` | `7.0.25` | Domain/public-suffix parsing and normalization | Canonical cache keys, host policy, and politeness bucketing |
| `cheerio` | `1.2.0` | HTML parsing and cleanup | Lightweight DOM cleanup pre/post extraction |
| `@mozilla/readability` | `0.6.0` | Main-content extraction | Primary article/content extraction from noisy pages |
| `turndown` | `7.2.2` | HTML-to-Markdown conversion | Consistent markdown output channel |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `p-retry` | Undici `RetryHandler` | Undici retry is solid for dispatcher-level requests, but `p-retry` is simpler for custom domain-aware retry policies |
| `@mozilla/readability` + `turndown` | Hand-rolled DOM extraction rules | Lower initial dependency count, but significantly worse robustness across site variants |
| `robots-parser` | Custom robots parser | Easy to start, error-prone on wildcard/precedence details |

**Installation:**
```bash
npm install undici zod p-retry p-queue pino robots-parser tldts cheerio @mozilla/readability turndown
```

## Architecture Patterns

### Recommended Project Structure
```
src/
├── sdk/                 # public search/fetch methods + contracts
├── core/                # retry, cache, policy, telemetry, concurrency
├── providers/serper/    # Serper transport + response mapping
├── scraper/             # fetch orchestration, robots, extraction, fallback
└── tests/               # unit + integration + stability contract tests
```

### Pattern 1: Contract-First Boundaries
**What:** Validate inputs at API boundary and validate/normalize outputs before returning.  
**When to use:** Every public method (`search`, `fetch`) and provider adapter boundary.  
**Example:**
```typescript
// Source: https://zod.dev/
import { z } from "zod";

export const SearchInput = z.object({
  query: z.string().min(1),
  options: z.object({
    limit: z.number().int().positive().max(20).default(10),
    country: z.string().length(2).optional(),
    language: z.string().optional(),
  }).default({}),
});

export const SearchResult = z.object({
  title: z.string().min(1),
  url: z.string().url(),
  snippet: z.string().default(""),
  rank: z.number().int().positive(),
});
```

### Pattern 2: Provider Adapter + Internal Mapping Layer
**What:** Keep Serper wire payload private; map `organic[]` into SDK contract fields and canonical ranks.  
**When to use:** Immediately after Serper response deserialization.  
**Example:**
```typescript
// Source: https://serper.dev/ (example payload includes organic[].title/link/snippet/position)
type SerperOrganic = { title?: string; link?: string; snippet?: string; position?: number };

function mapSerperOrganic(organic: SerperOrganic[], limit: number) {
  return organic
    .slice(0, limit)
    .map((item, i) => ({
      title: item.title?.trim() ?? "",
      url: item.link ?? "",
      snippet: item.snippet ?? "",
      rank: item.position ?? i + 1,
    }))
    .filter((r) => r.title && r.url);
}
```

### Pattern 3: HTTP-First Fetch Orchestrator with Explicit Fallback Reason
**What:** Gate by robots and URL policy, attempt HTTP extraction first, fallback only on declared conditions.  
**When to use:** All `fetch(url, options)` calls.  
**Example:**
```typescript
// Sources: https://www.npmjs.com/package/robots-parser, https://registry.npmjs.org/p-retry/latest
async function fetchContent(url: string) {
  const policy = await evaluateRobots(url); // allowed + crawlDelay
  if (!policy.allowed) throw new Error("ROBOTS_DISALLOW");

  const httpResult = await tryHttpExtraction(url);
  if (httpResult.ok && httpResult.quality >= 0.5) return httpResult;

  // fallback reason should be machine-readable: NETWORK_ERROR or LOW_CONTENT_QUALITY
  return runBrowserFallback(url, httpResult.reason);
}
```

### Anti-Patterns to Avoid
- **Leaking provider payloads:** Returning Serper-specific fields breaks SDK stability when provider format changes.
- **Browser-first fetching:** Increases cost/latency and violates phase constraints.
- **Implicit retries without limits:** Causes unpredictable timing and rate-limit amplification.
- **Unstable rank behavior:** Recomputing/reshuffling ranks inconsistently across runs creates flaky downstream behavior.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Runtime schema validation | Custom `if`/`typeof` trees | `zod` | Safer contracts, better errors, shared types |
| Retry/backoff logic | Ad-hoc `while` loops with sleep | `p-retry` | Handles retry budgets, aborts, and policy hooks |
| Concurrency/rate limiting | Manual semaphore counters | `p-queue` | Battle-tested queue + interval caps |
| Robots parsing | String matching in `robots.txt` | `robots-parser` | Correct wildcard/precedence handling |
| Main content extraction | Site-specific CSS selector heuristics only | `@mozilla/readability` + `cheerio` | Better generalization across diverse HTML |
| Markdown conversion | Custom HTML traversal | `turndown` | Consistent markdown output and rule extension |

**Key insight:** Most retrieval bugs come from edge cases (URL forms, robots semantics, malformed HTML, retry storms), and these libraries already encode years of edge-case handling.

## Common Pitfalls

### Pitfall 1: Non-Deterministic Normalization
**What goes wrong:** Equivalent inputs produce different ordering/fields between runs.  
**Why it happens:** Missing canonicalization (query/options, URL format, rank fallback) and unstable mapping defaults.  
**How to avoid:** Canonical cache keys, stable sorting, explicit defaults, and rank derivation rules.  
**Warning signs:** Snapshot test churn and intermittent ordering diffs.

### Pitfall 2: Retrying the Wrong Failures
**What goes wrong:** Retries waste time or amplify failures (e.g., retrying permanent 4xx).  
**Why it happens:** Retry policy is transport-generic, not domain-aware.  
**How to avoid:** Retry on network + 429/5xx only; short bounded budgets; respect server hints.  
**Warning signs:** Latency spikes and repeated identical failures.

### Pitfall 3: Robots/Politeness Applied Too Late
**What goes wrong:** Outbound requests happen before allow/disallow checks.  
**Why it happens:** Robots evaluation is bolted on after fetch logic.  
**How to avoid:** Make policy gate an explicit first stage in fetch orchestration.  
**Warning signs:** Logs show HTTP requests for disallowed paths.

### Pitfall 4: Extraction Shape Drift
**What goes wrong:** `fetch` returns inconsistent fields (`text`, `markdown`, metadata) by content type/path.  
**Why it happens:** No single normalized response schema across code paths.  
**How to avoid:** Single `FetchResponse` schema and map all extraction outcomes into it.  
**Warning signs:** Consumer code needs branch-specific null checks.

### Pitfall 5: Overshared Logging
**What goes wrong:** Logs include secrets or large raw bodies.  
**Why it happens:** Debug logging not constrained by redaction/size limits.  
**How to avoid:** Structured logs with explicit field allowlist and body-size caps.  
**Warning signs:** Sensitive headers/raw content appearing in logs.

## Code Examples

Verified patterns from official sources:

### Bounded Retry for HTTP Provider Calls
```typescript
// Source: https://registry.npmjs.org/p-retry/latest
import pRetry, { AbortError } from "p-retry";

async function callSerperWithRetry(run: () => Promise<Response>) {
  return pRetry(async () => {
    const res = await run();
    if (res.status === 400 || res.status === 401 || res.status === 403) {
      throw new AbortError(`Non-retriable status: ${res.status}`);
    }
    if (!res.ok) throw new Error(`Retryable status: ${res.status}`);
    return res;
  }, { retries: 3, minTimeout: 250, factor: 2 });
}
```

### Queue-Based Concurrency Cap
```typescript
// Source: https://registry.npmjs.org/p-queue/latest
import PQueue from "p-queue";

const queue = new PQueue({ concurrency: 4, intervalCap: 20, interval: 1000 });

export function enqueueFetch<T>(job: () => Promise<T>) {
  return queue.add(job);
}
```

### Robots + Extraction Flow
```typescript
// Sources: https://www.npmjs.com/package/robots-parser, https://registry.npmjs.org/@mozilla%2Freadability/latest
import robotsParser from "robots-parser";
import { JSDOM } from "jsdom";
import { Readability } from "@mozilla/readability";

async function extractMainText(pageUrl: string, robotsTxt: string, html: string) {
  const robots = robotsParser(new URL("/robots.txt", pageUrl).toString(), robotsTxt);
  if (robots.isAllowed(pageUrl, "web-agent-bot") === false) {
    throw new Error("ROBOTS_DISALLOW");
  }

  const doc = new JSDOM(html, { url: pageUrl }).window.document;
  const article = new Readability(doc).parse();
  return article?.textContent ?? "";
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Compile-time-only TypeScript typing | Runtime schema validation with `zod` contracts | Matured through 2024-2026 TS SDK practices | Detects API drift and malformed data at boundaries |
| Naive retry loops | Policy-based retries (`p-retry` / Undici retry configs) | Widely standardized pre-2026 | Better resilience with bounded cost/latency |
| One-off parsing selectors | Readability-first extraction with normalization | Established approach for article-like pages | More stable text extraction across varied sites |
| Unbounded parallel fetching | Queue-driven concurrency/rate limits (`p-queue`) | Mainstream in API/scraping workloads | Reduces throttling and infrastructure instability |

**Deprecated/outdated:**
- **Provider-shaped SDK output:** Replaced by normalized contracts to preserve API stability.
- **Browser-first scraping pipelines:** Replaced by HTTP-first for cost, latency, and maintainability.

## Open Questions

1. **Serper official request/response contract depth**
   - What we know: Homepage examples show `organic[].title/link/snippet/position` and related fields.
   - What's unclear: Full parameter matrix and hard guarantees around optional fields in all result modes.
   - Recommendation: Add a thin Serper contract test fixture from real API responses before freezing v1 mapping.

2. **Determinism policy for dynamic SERP content**
   - What we know: Equivalent requests can still receive fresh live results over time.
   - What's unclear: Whether Phase 01 "stability" expects deterministic mapping only or deterministic data snapshots.
   - Recommendation: Define stability scope explicitly as "stable mapping/shape for equivalent provider payloads."

3. **Browser fallback trigger threshold**
   - What we know: Fallback should be selective and reasoned.
   - What's unclear: Exact quality threshold for "low content quality" in v1.
   - Recommendation: Start with simple measurable threshold (e.g., minimum extracted text length) and tune in later phases.

## Sources

### Primary (HIGH confidence)
- [https://registry.npmjs.org/undici/latest](https://registry.npmjs.org/undici/latest) - current version and official README content
- [https://undici.nodejs.org/#/docs/api/RetryHandler](https://undici.nodejs.org/#/docs/api/RetryHandler) - retry defaults and behavior
- [https://undici.nodejs.org/#/docs/api/Fetch](https://undici.nodejs.org/#/docs/api/Fetch) - fetch API behavior in Undici
- [https://zod.dev/](https://zod.dev/) and [https://registry.npmjs.org/zod/latest](https://registry.npmjs.org/zod/latest) - Zod 4 stability and usage
- [https://registry.npmjs.org/p-retry/latest](https://registry.npmjs.org/p-retry/latest) - retry API and defaults
- [https://registry.npmjs.org/p-queue/latest](https://registry.npmjs.org/p-queue/latest) - queue/rate-limit API and options
- [https://registry.npmjs.org/robots-parser/latest](https://registry.npmjs.org/robots-parser/latest) - robots parsing capabilities and API
- [https://registry.npmjs.org/tldts/latest](https://registry.npmjs.org/tldts/latest) - URL/domain parsing APIs
- [https://registry.npmjs.org/cheerio/latest](https://registry.npmjs.org/cheerio/latest) - HTML parsing usage and current version
- [https://registry.npmjs.org/%40mozilla%2Freadability/latest](https://registry.npmjs.org/%40mozilla%2Freadability/latest) - extraction library metadata/version
- [https://registry.npmjs.org/turndown/latest](https://registry.npmjs.org/turndown/latest) - markdown conversion API/version
- [https://registry.npmjs.org/pino/latest](https://registry.npmjs.org/pino/latest) - structured logging package/version

### Secondary (MEDIUM confidence)
- [https://serper.dev/](https://serper.dev/) - provider payload examples and operational characteristics (latency/real-time claims)

### Tertiary (LOW confidence)
- Web discovery results for Serper integration docs outside serper.dev (used only to identify leads; not treated as authoritative)

## Metadata

**Confidence breakdown:**
- Standard stack: **HIGH** - Based on official package docs/registry and established ecosystem usage.
- Architecture: **MEDIUM** - Strongly supported by docs + project constraints, but specific Serper contract details are partially inferred from public examples.
- Pitfalls: **MEDIUM** - Supported by official library behavior and common retrieval failure modes; some items are operational best practice rather than explicit vendor guidance.

**Research date:** 2026-03-15  
**Valid until:** 2026-04-14
