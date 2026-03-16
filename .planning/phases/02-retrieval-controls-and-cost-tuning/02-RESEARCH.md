# Phase 02: Retrieval Controls and Cost Tuning - Research

**Researched:** 2026-03-15  
**Domain:** Search/fetch control surfaces for cost, latency, scope, locale, freshness, and cache behavior in a TypeScript SDK  
**Confidence:** MEDIUM

## Summary

Phase 02 should be planned as a control-plane layer on top of Phase 01 retrieval primitives: normalize options, enforce bounded execution, and map controls to provider/fetch behavior in a deterministic way. The key planning target is not "more knobs", but predictable tradeoffs per call (`faster/cheaper` vs `fresher/broader`) with safe defaults.

For `search`, the standard approach is: cap breadth (`maxResults`), cap latency (`timeoutMs` with abort), apply scope constraints (`includeDomains`/`excludeDomains`), and apply locale/freshness controls while defaulting to US + English. Serper remains provider-only in v1, so all provider details stay internal and SDK options remain provider-agnostic.

For `fetch`, `REL-03` is best implemented with explicit cache policy options and a canonical cache key strategy. Use `maxAgeMs` as freshness bound and `fresh: true` (force-fresh) as cache bypass. This should be implemented in-process with a battle-tested cache library and explicit semantics for hit/miss/bypass.

**Primary recommendation:** Implement a single normalized `RetrievalControls` policy object consumed by both `search` and `fetch`, with strict defaults, explicit bounds, and deterministic mapping to provider/query/cache behaviors.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `undici` | `7.16.0` | HTTP transport for provider/search/fetch calls | Official Node HTTP client with first-class fetch/request support |
| `AbortSignal.timeout()` (platform API) | Baseline 2024+ | Hard per-call timeout control | Standard cancellation primitive for latency caps |
| `zod` | `4.x` | Validate and normalize options/defaults | Prevents invalid control combinations and keeps behavior deterministic |
| `lru-cache` | `11.2.7` | In-process cache for `maxAge` and bypass policies | Mature cache implementation with TTL + stale/revalidate primitives |
| `tldts` | `7.0.25` | Domain parsing/canonicalization for include/exclude logic | Correct handling of suffix/subdomain edge cases |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `p-queue` | `9.1.0` | Queue-level concurrency and interval caps | If Phase 02 includes queue-based throttling around provider calls |
| `p-retry` | `7.1.1` | Retry behavior with abort hooks | Keep retries bounded under timeout budgets |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `lru-cache` | custom `Map` + `setTimeout` TTL cache | Simpler initially, but more edge cases and weaker observability/control |
| Query operator domain filtering (`site:` / `-site:`) | Provider-native domain filters (if available) | Native filters are cleaner; operator approach is portable but less strict |
| `AbortSignal.timeout()` | manual `AbortController` + timers | Manual approach works but is noisier and easier to get wrong |

**Installation:**
```bash
npm install undici zod lru-cache tldts p-queue p-retry
```

## Architecture Patterns

### Recommended Project Structure
```
src/
├── sdk/contracts/            # Search/fetch options schemas and defaults
├── core/policy/              # Retrieval controls normalization + bounds
├── core/cache/               # Cache keying + maxAge/fresh policies
├── providers/serper/         # Control mapping to Serper request shape
└── tests/                    # Option matrix + policy behavior tests
```

### Pattern 1: Normalize-Then-Execute Controls
**What:** Parse user options once into an internal normalized control object (`ResolvedControls`) before any network call.  
**When to use:** Every `search(...)` and `fetch(...)` entry point.  
**Example:**
```typescript
// Source: https://zod.dev/
import { z } from "zod";

const SearchControls = z.object({
  maxResults: z.number().int().min(1).max(20).default(10),
  timeoutMs: z.number().int().min(250).max(10_000).default(2_500),
  includeDomains: z.array(z.string()).default([]),
  excludeDomains: z.array(z.string()).default([]),
  country: z.string().length(2).default("us"),
  language: z.string().length(2).default("en"),
  freshness: z.enum(["any", "day", "week", "month", "year"]).default("any"),
});
```

### Pattern 2: Domain Scope as Canonical Policy
**What:** Canonicalize domain lists before query shaping, then enforce include/exclude in both request shaping and post-filtering.  
**When to use:** CTRL-02 implementation for search result scope control.  
**Example:**
```typescript
// Source: https://www.npmjs.com/package/tldts
import { getDomain } from "tldts";

function normalizeDomain(input: string): string {
  return getDomain(input, { allowPrivateDomains: true })?.toLowerCase() ?? "";
}
```

### Pattern 3: Cache Policy Object for Fetch Freshness
**What:** Represent cache behavior explicitly as policy (`maxAgeMs`, `fresh`) and apply before outbound fetch.  
**When to use:** REL-03 for `fetch(url, options)`.  
**Example:**
```typescript
// Source: https://www.npmjs.com/package/lru-cache
import { LRUCache } from "lru-cache";

const cache = new LRUCache<string, string>({ max: 500, ttl: 5 * 60 * 1000 });

async function getWithPolicy(key: string, fresh: boolean): Promise<string | undefined> {
  if (!fresh) return cache.get(key);
  return undefined; // bypass cache when force-fresh is requested
}
```

### Anti-Patterns to Avoid
- **Unbounded controls:** Accepting arbitrary `maxResults`/timeouts creates cost and latency blowups.
- **String-level domain filtering:** Comparing raw hosts without canonicalization causes leaks and false matches.
- **Hidden default behavior:** Not documenting defaults (US + English) makes result changes look random.
- **Ambiguous cache semantics:** Mixing `no-cache`, `no-store`, and custom flags without clear mapping causes stale/fresh confusion.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Timeout/cancel plumbing | Custom timer wrappers around promises everywhere | `AbortSignal.timeout()` | Standardized timeout semantics and cleaner cancellation |
| Domain parsing | Regex/split-based host parsing | `tldts` | Handles PSL/private suffix, IDNA, IP edge cases |
| TTL+LRU caching | Ad-hoc object/map cache with manual eviction | `lru-cache` | Safer bounds, TTL behavior, and stale/revalidate support |
| Queue rate throttling | DIY token bucket and counters | `p-queue` | Concurrency + interval controls are already solved |
| Retry orchestration | Custom retry loops | `p-retry` | Retry budgets, hook points, and abort integration |

**Key insight:** Control surfaces are easy to expose but hard to keep deterministic under edge cases; mature primitives reduce ambiguity and production drift.

## Common Pitfalls

### Pitfall 1: Timeout does not bound total wall time
**What goes wrong:** A request times out, but retries continue and blow up p95 latency/cost.  
**Why it happens:** Timeout is applied per attempt, not as end-to-end budget.  
**How to avoid:** Treat timeout as a hard budget and pass abort signals through retry layers.  
**Warning signs:** Calls exceed configured timeout by 2-4x during failures.

### Pitfall 2: Include/exclude domain controls are bypassed
**What goes wrong:** Results outside allowed scope leak through.  
**Why it happens:** Scope only applied in query shaping, not validated on returned URLs.  
**How to avoid:** Apply domain policy twice: query-time and post-result filter-time.  
**Warning signs:** Returned URLs include blocked domains under mixed subdomain cases.

### Pitfall 3: Locale defaults drift
**What goes wrong:** Behavior changes by runtime environment or provider defaults.  
**Why it happens:** Country/language defaults are implicit instead of pinned.  
**How to avoid:** Hard-default `country=us`, `language=en` at schema level, and always send normalized values.  
**Warning signs:** Snapshot/result shifts between environments with same input query.

### Pitfall 4: Freshness option semantics are undocumented
**What goes wrong:** `freshness` option exists but users cannot predict impact.  
**Why it happens:** Mapping to provider query parameters/operators is implicit.  
**How to avoid:** Document exact mapping and test each freshness mode against request payload snapshots.  
**Warning signs:** Freshness mode changes produce inconsistent or no measurable difference.

### Pitfall 5: Cache bypass and maxAge conflict
**What goes wrong:** `fresh: true` still returns cached data, or `maxAge` silently ignored.  
**Why it happens:** Cache policy precedence is not explicit.  
**How to avoid:** Define precedence (`fresh: true` overrides cache read), and encode it in unit tests.  
**Warning signs:** Repeated "force fresh" calls show cache-hit telemetry.

## Code Examples

Verified patterns from official sources:

### Timeout-Capped Fetch
```typescript
// Source: https://developer.mozilla.org/en-US/docs/Web/API/AbortSignal/timeout_static
const response = await fetch(url, {
  signal: AbortSignal.timeout(timeoutMs),
});
```

### Queue-Based Concurrency + Interval Cap
```typescript
// Source: https://www.npmjs.com/package/p-queue
import PQueue from "p-queue";

const queue = new PQueue({
  concurrency: 4,
  intervalCap: 20,
  interval: 1000,
  timeout: 2500,
});
```

### Search Query Domain Operators
```typescript
// Sources: https://support.google.com/websearch/answer/2466433?p=adv_operators
// Include domains: site:example.com
// Exclude domains: -site:example.com
function withDomainScope(query: string, include: string[], exclude: string[]) {
  const includes = include.map((d) => `site:${d}`).join(" ");
  const excludes = exclude.map((d) => `-site:${d}`).join(" ");
  return [query, includes, excludes].filter(Boolean).join(" ").trim();
}
```

### Cache-Control Semantics for Fresh vs Cached
```typescript
// Source: https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Cache-Control
// fresh=true -> bypass local cache read (analogous to "no-cache" revalidation intent)
// maxAgeMs -> accept cached entry only if age <= maxAgeMs
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Hard-coded retrieval behavior | User-facing retrieval controls with safe defaults | 2024-2026 SDK UX shift | Better cost/latency governance by callers |
| Naive host string matching | PSL-aware domain normalization (`tldts`) | Broad adoption by 2025 | Fewer domain scope bugs |
| Ad-hoc in-memory caches | Bounded TTL/LRU caches with explicit policy | Matured pre-2026 | Predictable freshness/cost tradeoffs |
| Manual timer cancellation | `AbortSignal.timeout()` standardized use | Baseline 2024+ | Cleaner timeout handling and less boilerplate |

**Deprecated/outdated:**
- **Implicit locale behavior:** replace with explicit schema defaults (`us`, `en`).
- **Undocumented freshness flags:** replace with tested, documented provider mapping.

## Open Questions

1. **Serper freshness parameter guarantees**
   - What we know: Serper publicly confirms real-time results and location/language customization.
   - What's unclear: Official, versioned parameter contract for freshness (for example, `tbs` mappings) is not publicly documented on `serper.dev`.
   - Recommendation: Treat freshness mapping as adapter-internal with snapshot tests, and mark behavior as "best effort" until official parameter docs are available.

2. **Serper-native domain filter support**
   - What we know: Google search operators (`site:`, `-`) are officially supported in query syntax.
   - What's unclear: Whether Serper provides explicit include/exclude domain fields beyond query composition.
   - Recommendation: Use operator-based query shaping plus strict post-filter enforcement on returned URLs.

3. **Scope of timeout budget**
   - What we know: `AbortSignal.timeout()` cleanly bounds one request path.
   - What's unclear: Whether Phase 02 should define timeout across retries/end-to-end or per outbound attempt.
   - Recommendation: Plan for end-to-end timeout budget semantics now to avoid Phase 3 behavior changes.

## Sources

### Primary (HIGH confidence)
- [https://serper.dev/](https://serper.dev/) - official provider positioning, real-time/no-cache claim, location/language customization claim
- [https://serper.dev/terms](https://serper.dev/terms) - reliability/accuracy disclaimers and licensing constraints
- [https://support.google.com/websearch/answer/2466433?p=adv_operators](https://support.google.com/websearch/answer/2466433?p=adv_operators) - official search operators (`site:` and `-` exclusion)
- [https://support.google.com/websearch/answer/13485060](https://support.google.com/websearch/answer/13485060) - language filtering behavior context
- [https://developer.mozilla.org/en-US/docs/Web/API/AbortSignal/timeout_static](https://developer.mozilla.org/en-US/docs/Web/API/AbortSignal/timeout_static) - timeout semantics and error behavior
- [https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Cache-Control](https://developer.mozilla.org/en-US/docs/Web/HTTP/Reference/Headers/Cache-Control) - cache directives and freshness/revalidation semantics
- [https://www.npmjs.com/package/lru-cache](https://www.npmjs.com/package/lru-cache) - TTL/LRU behavior and caveats
- [https://www.npmjs.com/package/tldts](https://www.npmjs.com/package/tldts) - domain parsing/canonicalization API
- [https://www.npmjs.com/package/p-queue](https://www.npmjs.com/package/p-queue) - queue timeout/concurrency/interval controls
- [https://www.npmjs.com/package/p-retry](https://www.npmjs.com/package/p-retry) - bounded retry behavior and abort integration
- [https://www.npmjs.com/package/undici](https://www.npmjs.com/package/undici) - transport baseline for Node SDK

### Secondary (MEDIUM confidence)
- Existing project research docs in `.planning/research` - stack/architecture continuity for this repo's v1 constraints.

### Tertiary (LOW confidence)
- Community wrappers and third-party references for Serper parameter details (used to identify likely mappings, not treated as authoritative).

## Metadata

**Confidence breakdown:**
- Standard stack: **HIGH** - Backed by official package docs and platform documentation.
- Architecture: **MEDIUM** - Strong pattern confidence, but some Serper parameter details remain undocumented publicly.
- Pitfalls: **MEDIUM** - Operationally common and supported by standards/docs, but provider-specific edge behavior still needs local validation.

**Research date:** 2026-03-15  
**Valid until:** 2026-04-14
