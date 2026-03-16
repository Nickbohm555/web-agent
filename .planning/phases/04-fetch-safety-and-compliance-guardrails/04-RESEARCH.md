# Phase 4: Fetch Safety and Compliance Guardrails - Research

**Researched:** 2026-03-15  
**Domain:** Node.js fetch safety (SSRF guardrails) + robots/compliance enforcement  
**Confidence:** HIGH

## Summary

Phase 04 should be planned as a strict preflight-and-policy layer in front of outbound fetch execution. The critical design choice is to make safety/compliance checks first-class outcomes, not hidden internals. That means every disallow condition (URL policy reject, network/IP reject, robots deny, robots unavailable policy) returns explicit typed outcomes that developers can inspect programmatically.

The standards baseline is clear: use WHATWG URL parsing from Node, enforce host/IP safety after DNS resolution (and on every redirect hop), and evaluate robots rules with RFC 9309 semantics. OWASP SSRF guidance strongly favors allowlist-first design and recommends disabling automatic redirects in the HTTP client unless each redirect is revalidated. RFC 9309 clarifies group matching, most-specific Allow/Disallow resolution, redirect behavior for robots fetch, and handling of unreachable robots files.

The implementation should prioritize a policy engine with deterministic decisions, a resolver/classifier layer for SSRF protections, and a robots evaluator that produces explicit allow/deny/unknown states. This decomposition makes tests straightforward and prevents accidental fetch execution before policy verdicts.

**Primary recommendation:** Build `fetch` around an explicit `SafetyDecision` + `ComplianceDecision` preflight pipeline that must return allow before network execution.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `node:url` (WHATWG URL) | Node 24 LTS | Canonical URL parse/normalize | Avoids regex parsers; consistent parsing semantics in runtime |
| `node:dns` / `node:dns/promises` | Node 24 LTS | Resolve hostnames to concrete IPs pre-connect | Needed to enforce SSRF guardrails on resolved targets |
| `undici` | 7.24.3 | HTTP client + redirect/DNS hooks | Modern Node HTTP path; supports dispatcher/interceptor patterns |
| `robots-parser` | 3.0.1 | RFC-style robots rule evaluation | Battle-tested Allow/Disallow matching with wildcard support |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `tldts` | 7.0.25 | Domain/hostname normalization and classification | Domain policy checks and allow/deny list logic |
| `ipaddr.js` | 2.3.0 | IP range classification (private/loopback/reserved) | Robust SSRF IP checks across IPv4/IPv6 formats |
| `node:net` (`BlockList`, `isIP`) | Node 24 LTS | Native IP/subnet checks and block rules | Lightweight baseline blocklist checks without custom parsers |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `robots-parser` | Custom REP parser | High risk of spec mismatch; unnecessary complexity vs maintained parser |
| `ipaddr.js` | Hand-rolled CIDR math | Easy to miss IPv6/encoded edge cases; security-critical failure mode |
| `undici` policy wrapper | Native `fetch` only wrappers | Less control over redirect handling and request lifecycle integration |

**Installation:**
```bash
npm install undici robots-parser tldts ipaddr.js
```

## Architecture Patterns

### Recommended Project Structure
```
src/
├── core/policy/                  # URL/network policy models and decision engine
├── core/network/                 # DNS resolve + IP classification + redirect validation
├── scraper/robots/               # robots fetch/cache/evaluator
├── sdk/contracts/                # typed allow/deny outcomes and errors
└── tests/safety/                 # SSRF + robots behavior tests
```

### Pattern 1: Preflight Policy Gate (Fail Closed)
**What:** Evaluate URL syntax/scheme/host/domain/IP policies before any outbound request.  
**When to use:** Every `fetch(...)` call, before constructing request execution.  
**Example:**
```typescript
// Source: https://nodejs.org/api/url.html, https://owasp.org/www-community/pages/controls/SSRF_Prevention_in_Nodejs
const target = new URL(inputUrl);
if (!["http:", "https:"].includes(target.protocol)) {
  return deny("UNSAFE_SCHEME", { protocol: target.protocol });
}
if (target.username || target.password) {
  return deny("CREDENTIALS_IN_URL");
}
```

### Pattern 2: Resolve-Then-Classify SSRF Guardrail
**What:** Resolve hostname to IP(s), classify each candidate IP, block private/local/link-local/reserved/metadata targets.  
**When to use:** Before connect and again on each redirect hop.  
**Example:**
```typescript
// Source: https://nodejs.org/api/dns.html, https://nodejs.org/api/net.html, https://www.rfc-editor.org/rfc/rfc1918
const answers = await dns.lookup(hostname, { all: true });
for (const answer of answers) {
  if (isDisallowedAddress(answer.address)) {
    return deny("SSRF_BLOCKED_IP", { ip: answer.address });
  }
}
```

### Pattern 3: Redirect-Aware Revalidation
**What:** Disable automatic blind redirects, or cap redirects and re-run full safety checks per hop.  
**When to use:** Any request that can receive `3xx`.  
**Example:**
```typescript
// Source: https://raw.githubusercontent.com/nodejs/undici/main/docs/docs/api/Dispatcher.md
const client = new Client(origin).compose(
  interceptors.redirect({ maxRedirections: 0 })
);
// Manual redirect loop: validate -> request -> inspect Location -> validate next hop
```

### Pattern 4: Explicit Robots Decision Model
**What:** Parse robots and return explicit `allow | deny | unavailable | invalid` decision states with reason metadata.  
**When to use:** Before fetch body retrieval (or as part of staged fetch).  
**Example:**
```typescript
// Source: https://raw.githubusercontent.com/samclarke/robots-parser/master/README.md, https://datatracker.ietf.org/doc/html/rfc9309
const robots = robotsParser(robotsTxtUrl, body);
const allowed = robots.isAllowed(targetUrl, userAgentToken);
if (allowed === false) return deny("ROBOTS_DENY");
if (allowed === undefined) return outcome("ROBOTS_UNKNOWN");
return allow("ROBOTS_ALLOW");
```

### Anti-Patterns to Avoid
- **String/regex URL validation:** Bypass-prone for encoding and parser edge cases; always parse with `new URL(...)`.
- **Hostname-only SSRF checks:** Must resolve and validate resulting IPs, including IPv6 and mapped addresses.
- **One-time validation only:** Redirect hops can pivot to blocked destinations unless every hop is rechecked.
- **Implicit robots handling:** Silent skip/ignore creates non-compliant behavior; always expose explicit compliance outcome.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| REP parser | Custom robots grammar/matcher | `robots-parser` + RFC 9309 rules | Rule precedence/encoding/wildcard semantics are easy to get wrong |
| IP range math | Manual CIDR/IPv6 checks | `ipaddr.js` and/or `net.BlockList` | Security-sensitive edge cases across IPv4/IPv6 formats |
| Domain parsing | Homegrown hostname splitting | `tldts` | Handles IDNA/public suffix edge cases correctly |
| Redirect policy | Blind `fetch` auto-follow | Undici interceptors/manual redirect loop | Needed to revalidate each redirect target for SSRF safety |

**Key insight:** Safety/compliance failures are mostly edge-case failures; established libraries encode those edge cases better than custom logic.

## Common Pitfalls

### Pitfall 1: DNS Rebinding Blind Spot
**What goes wrong:** Validation checks hostname only, then connect resolves to private/internal IP.  
**Why it happens:** No resolve-and-classify step or no revalidation at connect/redirect time.  
**How to avoid:** Resolve before request, classify every resolved address, and re-check each redirect hop.  
**Warning signs:** Requests to public hostnames occasionally hit RFC1918 or loopback addresses.

### Pitfall 2: Redirect Safety Bypass
**What goes wrong:** Initial URL is safe, redirected URL is unsafe but still fetched.  
**Why it happens:** Client auto-follows redirects without policy hook.  
**How to avoid:** Set redirect limit to 0 or intercept redirects and run full safety policy per `Location`.  
**Warning signs:** No test coverage for `3xx` to internal/private destinations.

### Pitfall 3: Robots Semantics Mismatch
**What goes wrong:** Wrong allow/deny decision for overlapping rules or user-agent matching.  
**Why it happens:** Non-spec matching logic (not longest match, wrong case behavior).  
**How to avoid:** Use parser behavior aligned to RFC 9309 and test longest-match examples.  
**Warning signs:** Inconsistent decisions between equivalent path encodings.

### Pitfall 4: Fail-Open on Robots Fetch Errors
**What goes wrong:** robots file unreachable but crawler proceeds without explicit policy decision.  
**Why it happens:** Network errors treated as "no file" and silently allowed.  
**How to avoid:** Introduce explicit policy for `robots_unreachable` and surface outcome to caller.  
**Warning signs:** Missing typed outcome for robots timeout/5xx.

### Pitfall 5: Opaque Errors
**What goes wrong:** Caller only gets generic fetch failure, cannot distinguish policy block vs network failure.  
**Why it happens:** Policy and transport errors share same untyped exception path.  
**How to avoid:** Typed error/outcome enums (`URL_POLICY_DENY`, `SSRF_BLOCKED_IP`, `ROBOTS_DENY`, etc.).  
**Warning signs:** App code cannot branch behavior by deny reason.

## Code Examples

Verified patterns from official sources:

### URL Parse + Protocol Guard
```typescript
// Source: https://nodejs.org/api/url.html
export function parseHttpUrl(raw: string): URL {
  const url = new URL(raw);
  if (url.protocol !== "http:" && url.protocol !== "https:") {
    throw new Error(`Unsupported scheme: ${url.protocol}`);
  }
  return url;
}
```

### DNS Resolution Prior to Policy Decision
```typescript
// Source: https://nodejs.org/api/dns.html
import dns from "node:dns/promises";

const records = await dns.lookup(hostname, { all: true });
// records: [{ address: "...", family: 4|6 }, ...]
```

### Undici Redirect Interceptor Configuration
```typescript
// Source: https://raw.githubusercontent.com/nodejs/undici/main/docs/docs/api/Dispatcher.md
import { Client, interceptors } from "undici";

const client = new Client("https://example.com").compose(
  interceptors.redirect({ maxRedirections: 0, throwOnMaxRedirects: true })
);
```

### Robots Allow/Deny Evaluation
```typescript
// Source: https://raw.githubusercontent.com/samclarke/robots-parser/master/README.md
import robotsParser from "robots-parser";

const robots = robotsParser(robotsUrl, robotsBody);
const verdict = robots.isAllowed(targetUrl, "MyBot");
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Regex/substring URL checks | WHATWG URL parsing + normalized policy checks | Matured as default Node best practice | Fewer parser bypasses and normalization bugs |
| Hostname-only denylist | Resolve-to-IP + CIDR/range classification + redirect revalidation | OWASP SSRF guidance consolidated over recent years | Stronger SSRF posture, better cloud metadata protection |
| Ad hoc robots handling | RFC 9309-aligned parsing and explicit outcomes | RFC 9309 published Sep 2022 | Predictable compliance behavior and clearer contracts |

**Deprecated/outdated:**
- URL regex validators for security policy: bypass-prone and not sufficient for SSRF controls.
- Blind redirect following in safety-sensitive fetch paths: must be policy-mediated.

## Open Questions

1. **Robots unreachable policy default**
   - What we know: RFC 9309 states unreachable robots can imply complete disallow for crawlers.
   - What's unclear: Product-level default for this SDK (`deny`, `allow with warning`, or configurable).
   - Recommendation: Default to deny in safety mode and allow explicit override in options.

2. **Private network exceptions**
   - What we know: Some users may legitimately fetch internal hosts.
   - What's unclear: Whether v1 should expose allowlist exceptions and at what granularity (CIDR/domain).
   - Recommendation: Keep v1 strict by default; plan opt-in `allowedCidrs`/`allowedHosts` with explicit risk labeling.

3. **Robots caching policy**
   - What we know: RFC 9309 allows caching and suggests not using cache beyond 24h unless unreachable.
   - What's unclear: Exact cache TTL and invalidation strategy for SDK ergonomics.
   - Recommendation: Plan configurable TTL with safe default (`<=24h`) and include outcome metadata (`cacheHit`, `fetchedAt`).

## Sources

### Primary (HIGH confidence)
- [Node URL API](https://nodejs.org/api/url.html) - canonical URL parsing behavior
- [Node DNS API](https://nodejs.org/api/dns.html) - hostname resolution behavior and APIs
- [Node Net API](https://nodejs.org/api/net.html) - `BlockList`, `isIP` primitives
- [Undici Dispatcher docs](https://raw.githubusercontent.com/nodejs/undici/main/docs/docs/api/Dispatcher.md) - redirect/dns interceptor patterns
- [Undici RedirectHandler docs](https://raw.githubusercontent.com/nodejs/undici/main/docs/docs/api/RedirectHandler.md) - redirect control parameters
- [RFC 9309](https://datatracker.ietf.org/doc/html/rfc9309) - REP matching, redirect, cache/error semantics
- [RFC 1918](https://www.rfc-editor.org/rfc/rfc1918) - private IPv4 ranges
- [robots-parser README](https://raw.githubusercontent.com/samclarke/robots-parser/master/README.md) - parser API semantics
- [tldts README](https://raw.githubusercontent.com/remusao/tldts/master/README.md) - domain parsing behavior
- [ipaddr.js README](https://raw.githubusercontent.com/whitequark/ipaddr.js/main/README.md) - IP classification utilities

### Secondary (MEDIUM confidence)
- [OWASP SSRF Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html) - practical SSRF defensive controls
- [OWASP SSRF Prevention in Node.js](https://owasp.org/www-community/pages/controls/SSRF_Prevention_in_Nodejs) - Node-oriented SSRF guidance

### Tertiary (LOW confidence)
- Web search discovery notes used only for URL discovery; all critical claims above were verified against primary/secondary sources.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - grounded in Node/Undici docs and package official READMEs/registry.
- Architecture: HIGH - directly derived from verified APIs and RFC/OWASP controls.
- Pitfalls: HIGH - repeatedly documented in OWASP and RFC behavior requirements.

**Research date:** 2026-03-15  
**Valid until:** 2026-04-14
