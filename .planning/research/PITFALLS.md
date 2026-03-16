# Pitfalls Research

**Domain:** low-cost, high-speed web search + scrape tooling for agent workflows (Serper + in-house TS SDK)
**Researched:** 2026-03-15
**Confidence:** MEDIUM

## Critical Pitfalls

### Pitfall 1: Optimizing for cost per query while relevance silently collapses

**What goes wrong:**
Teams optimize for throughput and cheap credits, but do not track answer quality. The system keeps "working" while agent outcomes degrade (wrong pages, thin snippets, stale or off-intent sources).

**Why it happens:**
Search APIs are treated as ground truth and eval is deferred. Serper itself states it does not warrant returned material accuracy/completeness/currentness, so blind trust creates hidden risk.

**How to avoid:**
Ship a relevance gate in v1:
- Define a golden query set by user intent cluster (transactional, factual, navigational, long-tail).
- Track `search -> fetch -> extraction -> agent answer` quality metrics weekly.
- Require source attribution and citation coverage thresholds before claiming success.
- Fail builds when relevance regression exceeds threshold.

**Warning signs:**
- Fewer user-visible failures but more "technically successful" runs with low-confidence answers.
- Rising fallback-to-"I couldn't find it" rate after throughput optimizations.
- Stable infra dashboards while support complaints about answer usefulness increase.

**Phase to address:**
Phase 3 - Relevance and Evaluation hardening.

---

### Pitfall 2: Missing explicit rate control and 429 discipline

**What goes wrong:**
Burst traffic triggers 429s, retries synchronize, and costs spike while latency explodes. Queue backlog grows faster than drain rate.

**Why it happens:**
Teams only cap concurrency but skip requests-per-minute controls, jittered backoff, and retry budgets. RFC 6585 defines 429 and optional `Retry-After`, but many clients ignore it.

**How to avoid:**
- Enforce both per-provider QPS and RPM token buckets.
- Respect `Retry-After` when present; otherwise apply exponential backoff + jitter.
- Add retry budget per job and per tenant.
- Circuit-break provider calls when error budgets are exceeded.

**Warning signs:**
- Repeating 429 bursts at minute boundaries.
- Identical retry timing across workers.
- Queue age increasing while worker count is unchanged.

**Phase to address:**
Phase 2 - Reliability guardrails.

---

### Pitfall 3: Robots/compliance handling implemented as "best effort"

**What goes wrong:**
Crawler policy behavior is inconsistent across domains, causing legal/compliance risk and unnecessary bans.

**Why it happens:**
Teams implement ad-hoc robots parsing and treat policy failures as "continue anyway". RFC 9309 has specific handling semantics teams often miss (for example, unreachable robots may require complete disallow behavior by crawler policy).

**How to avoid:**
- Implement robots policy as a first-class policy engine, not string matching.
- Cache robots decisions with TTL and host-level policy snapshots.
- Define explicit behaviors for 4xx unavailable vs 5xx/network unreachable.
- Log policy decisions per request for auditability.

**Warning signs:**
- Same URL fetched by one worker and blocked by another.
- Sudden host-wide block events after deploy.
- No audit trail showing why a fetch was allowed.

**Phase to address:**
Phase 2 - Compliance and policy layer.

---

### Pitfall 4: Treating HTML retrieval as successful extraction

**What goes wrong:**
Pipelines mark jobs successful after HTTP 200, but extracted content is boilerplate, challenge pages, cookie walls, or empty shells.

**Why it happens:**
Success is measured at transport layer only. Modern anti-bot systems and JS-heavy pages return deceptive "successful" responses.

**How to avoid:**
- Define extraction quality checks (min text length, language detection, DOM density, captcha/challenge signatures).
- Add extraction confidence score and block low-confidence payloads from downstream agent reasoning.
- Keep parser adapters per site class (news, docs, ecommerce) with contract tests.

**Warning signs:**
- Spike in very short extracted documents.
- Repeated tokens like "enable JavaScript" or "verify you are human".
- Answer quality drops while HTTP success remains high.

**Phase to address:**
Phase 1 - Fetch/extract contract design; Phase 3 - Quality gates.

---

### Pitfall 5: No canonicalization/dedup leads to wasted credits and loops

**What goes wrong:**
Equivalent URLs are fetched repeatedly (`utm_*`, fragments, tracking params), burning budget and increasing latency.

**Why it happens:**
Canonicalization is postponed. Teams assume queue uniqueness is enough, but uniqueness keys depend on normalization strategy.

**How to avoid:**
- Define canonical URL rules before queue insertion.
- Normalize query params, fragments, scheme/domain casing, and trailing slash policy.
- Use deterministic dedup keys tied to normalized URL + fetch mode.
- Track duplicate ratio as an SLO.

**Warning signs:**
- Same domain dominates spend with near-identical content hashes.
- Large queue growth with low unique document growth.
- Rising cost without proportional recall gain.

**Phase to address:**
Phase 1 - Core SDK contracts.

---

### Pitfall 6: Single-provider dependency (Serper-only) without degradation path

**What goes wrong:**
Any provider incident, policy change, or account issue becomes total outage for search.

**Why it happens:**
v1 shortcuts hard-code one backend and response schema with no adapter boundary.

**How to avoid:**
- Define provider interface in SDK (`search(query, opts)` with normalized output contract).
- Implement graceful degradation: cache, stale-while-revalidate, and optional fallback provider.
- Add provider health probes and route selection based on SLO + cost policy.

**Warning signs:**
- 100% of search traffic routed to one provider even during elevated errors.
- Emergency patches needed for minor schema/provider changes.
- No ability to replay jobs against alternate backends.

**Phase to address:**
Phase 4 - Multi-provider resilience.

---

### Pitfall 7: Exposing raw `fetch(url)` in SDK without SSRF containment

**What goes wrong:**
User-controlled URLs pivot into internal network access, cloud metadata endpoints, or local services.

**Why it happens:**
Teams prioritize developer speed and skip strict outbound policy design. URL validation is treated as input sanitization instead of network-control problem.

**How to avoid:**
- Enforce outbound allow/deny policy (scheme, host/IP, resolved IP class, port).
- Block private/link-local/metadata ranges and localhost targets by default.
- Disable unsafe redirects unless revalidated at each hop.
- Resolve DNS and re-check target on every redirect.

**Warning signs:**
- Requests to RFC1918/link-local addresses appear in logs.
- Unexplained hits to `169.254.169.254` or cloud metadata hostnames.
- Security exceptions tied to webhook/fetch features.

**Phase to address:**
Phase 1 - Secure fetch API design; Phase 2 - Security hardening.

---

### Pitfall 8: No provenance and licensing trail for returned content

**What goes wrong:**
Product cannot explain source lineage, attribution, or usage rights for downstream outputs.

**Why it happens:**
Source metadata is dropped between search results and extracted content. Teams assume "public web" implies safe reuse.

**How to avoid:**
- Persist source URL, retrieval timestamp, query context, and provider metadata for each chunk.
- Preserve attribution fields through every transformation.
- Enforce policy checks for restricted domains/content types before surfacing results.

**Warning signs:**
- Teams cannot answer "where did this answer come from?" quickly.
- Missing/stripped source fields in stored documents.
- Escalations about copyright/attribution with no audit chain.

**Phase to address:**
Phase 2 - Data governance and compliance.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Hard-code Serper response shape directly in app logic | Fast initial delivery | Provider lock-in and brittle upgrades | MVP spike only; replace before beta |
| Retry forever on transient errors | Higher short-term success rate | Retry storms, quota burn, hidden latency | Never |
| Skip canonicalization and dedup in v1 | Simpler fetch implementation | 20-50%+ wasted spend at scale | Only for tiny internal trials |
| Treat all fetches equally (no host policy tiers) | Minimal policy code | Legal/security incidents and host bans | Never |

## Integration Gotchas

Common mistakes when connecting to external services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Serper API | Assume "real-time" results are always accurate and complete | Treat as retrieval input; validate quality downstream and preserve fallbacks |
| Serper API quotas | Use account-level limit only | Implement per-tenant + per-job budgets and provider-level throttles |
| Site fetching | Consider HTTP 200 a success | Require extraction-quality validation and challenge-page detection |
| robots.txt | Parse only `Disallow` textually | Implement RFC-aware matching, host cache, and explicit unavailable/unreachable policy |
| Redirect handling | Validate only first URL | Re-validate destination host/IP on each redirect hop |

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Concurrency-only tuning (no RPM control) | Bursty 429s, periodic latency cliffs | Dual-limit throttling (QPS + RPM), queue smoothing | ~5-20 workers with shared key |
| No duplicate suppression | Spend rises faster than unique docs | Canonicalize URL and hash-based dedup | ~10k+ fetches/day |
| Centralized single queue with no priority lanes | High-value jobs starve | Priority queues by intent/tenant/SLA | Mixed workloads, >100 concurrent jobs |
| Synchronous post-processing on hot path | Throughput plateaus despite more workers | Async pipeline stages + bounded work queues | As soon as extraction/cleaning grows complex |

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Unrestricted outbound URL fetch | SSRF into internal/metadata services | Outbound policy engine, IP range blocking, per-hop redirect validation |
| Passing API keys in logs or query params | Credential leakage and abuse | Header-based auth only, redaction middleware, secret scanning |
| Shared API key across environments/tenants | Blast radius and quota abuse | Per-env/per-tenant scoped keys with rotation |
| No anti-abuse budget controls | Cost amplification attacks via prompt loops | Hard budget caps, anomaly alerts, kill switches |

## UX Pitfalls

Common user experience mistakes in this domain.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Opaque failure errors ("fetch failed") | Users cannot remediate | Return structured error taxonomy (`rate_limited`, `blocked`, `policy_denied`, `low_quality`) |
| No source confidence surfaced | Users over-trust bad answers | Expose source count, freshness, and extraction confidence |
| Hidden latency variability | Workflows feel randomly slow | Provide stage timings (`search_ms`, `fetch_ms`, `extract_ms`) and timeout hints |

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **`search` API:** Often missing query budget guardrails - verify per-job and per-tenant caps.
- [ ] **`fetch` API:** Often missing SSRF controls - verify private/link-local/metadata blocks and redirect revalidation.
- [ ] **Extraction:** Often missing quality gates - verify low-quality/challenge pages are rejected.
- [ ] **Reliability:** Often missing retry budgeting - verify bounded retries with jitter and circuit breaker behavior.
- [ ] **Compliance:** Often missing robots policy audit logs - verify allow/deny reason captured per request.
- [ ] **Provenance:** Often missing source lineage - verify each chunk stores URL + retrieval timestamp + provider metadata.

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Relevance collapse after infra optimization | HIGH | Freeze optimization rollout, replay golden set, diff stage metrics, roll back failing policy/model changes |
| Retry storm causing quota burn | MEDIUM | Activate global throttle, disable non-critical jobs, drain queue gradually, enforce retry budgets |
| Security incident from open fetch endpoint | HIGH | Disable external fetch path, rotate keys, block offending ranges, audit logs, ship policy gate before re-enable |
| Provider outage with no fallback | MEDIUM | Enter degraded mode (cache/stale), route to backup provider if available, replay failed jobs after recovery |

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Cost optimization before relevance controls | Phase 3 | Golden set regression suite blocks release on quality drop |
| 429/retry storm behavior | Phase 2 | Load test shows bounded retries and stable queue age under throttling |
| Robots/compliance inconsistency | Phase 2 | Policy test matrix passes for 4xx/5xx/unreachable robots cases |
| 200-but-useless extraction | Phase 1 and Phase 3 | Extraction quality score and rejection paths covered by tests |
| Missing canonicalization/dedup | Phase 1 | Duplicate ratio dashboard and canonicalization unit tests in CI |
| Single-provider lock-in | Phase 4 | Provider adapter swap test passes without app code changes |
| SSRF exposure in `fetch` | Phase 1 and Phase 2 | Security tests block private/link-local/metadata targets and unsafe redirects |
| Missing provenance/licensing trail | Phase 2 | Audit query can reconstruct source lineage for any generated answer |

## Sources

- [Serper homepage](https://serper.dev) (pricing/QPS/real-time/no-cache claims) - MEDIUM
- [Serper Terms of Service](https://serper.dev/terms) (accuracy disclaimer, usage restrictions, data license limits) - HIGH
- [RFC 9309 - Robots Exclusion Protocol](https://www.rfc-editor.org/rfc/rfc9309) (robots semantics, availability/unreachable handling, caching guidance) - HIGH
- [RFC 6585 - HTTP 429 Too Many Requests](https://www.rfc-editor.org/rfc/rfc6585) (retry semantics via `Retry-After`) - HIGH
- [Crawlee Scaling Guide](https://crawlee.dev/docs/guides/scaling-crawlers) (concurrency/minConcurrency/maxRequestsPerMinute guidance) - HIGH
- [Crawlee RequestQueue API](https://crawlee.dev/js/api/core/class/RequestQueue) (uniqueKey-based dedup behavior) - HIGH
- [OWASP SSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html) (allowlist strategy, redirect/DNS/IP protections, metadata endpoint risk) - HIGH
- Web ecosystem scans (2026) on scraping reliability and anti-bot operational failures - LOW (used for trend context only)

---
*Pitfalls research for: startup Serper + in-house scraper SDK*
*Researched: 2026-03-15*
