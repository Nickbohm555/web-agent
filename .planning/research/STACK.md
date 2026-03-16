# Stack Research

**Domain:** Cost-first web search + scrape SDK for agentic startup products
**Researched:** 2026-03-15
**Confidence:** HIGH

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Node.js | 24 LTS (allow 22 LTS fallback) | Runtime for SDK and scraper execution | Node `24` is Active LTS and aligns with modern fetch/runtime tooling; Node release policy favors LTS in production. **Confidence: HIGH** |
| TypeScript | `^5.7.0` (tested through 5.9) | Public SDK API contracts and internal type safety | TS-first SDK ergonomics are expected in 2025 for startup agent stacks; Zod 4 is tested against TS 5.5+ so this range stays compatible. **Confidence: HIGH** |
| Serper API | Current production API (single provider in v1) | Search retrieval (`search`) | Matches product constraint (single provider), and public pricing/throughput posture is strong for low-cost v1 launch. **Confidence: MEDIUM** |
| Undici | `^7.x` | High-throughput HTTP transport for both `search` and `fetch` | Official Node HTTP client; `undici.request()` gives better connection control/perf than generic clients and is ideal for cost-per-call optimization. **Confidence: HIGH** |
| Cheerio | `^1.1.0` (or newer 1.x) | Fast HTML parse + extraction for static pages | High adoption and low overhead for static-first scraping; keeps infra costs down versus browser-first extraction. **Confidence: HIGH** |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `p-retry` | `^7.1.0` | Exponential backoff with retry policy control | Retry `429/5xx` and transient network failures with bounded attempts and jitter. |
| `p-queue` | `^9.1.0` | Concurrency and interval caps | Enforce per-provider QPS and bounded local concurrency in SDK runtime. |
| `zod` | `^4.0.0` | Runtime validation + typed result schemas | Validate provider responses and options at SDK boundaries to prevent downstream breakage. |
| `robots-parser` | `^3.0.1` | `robots.txt` allow/disallow and crawl-delay checks | Respect crawl rules before fetch requests; keep legality/compliance logic explicit in v1. |
| `tldts` | `^7.0.0` | Domain parsing and normalization | Implement `includeDomains` / `excludeDomains` correctly across public suffix edge cases. |
| `@mozilla/readability` | `^0.6.0` | Article-body extraction fallback | Use only when simple selector extraction is noisy; avoid defaulting to heavy DOM pipelines. |
| `turndown` | `^7.2.0` | HTML-to-Markdown conversion | Generate compact, LLM-friendly page context output from extracted HTML. |
| `pino` | `^10.0.0` | Low-overhead structured logging | Keep observability cheap at high request volume; JSON logs are easy to pipe later. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| `tsdown` | Library bundling (ESM/CJS + types) | `tsup` now warns it is not actively maintained; for greenfield in 2025+, start on `tsdown` to avoid migration churn. |
| `vitest` | Unit/integration test runner | Fast TS-native test loop with good ecosystem alignment for SDK packages. |
| `msw` | HTTP mocking for tests | Deterministic provider/scrape test fixtures without patching app code paths. |
| `tsx` | Local TypeScript execution | Fast scripts/dev harnesses without build step. |

## Installation

```bash
# Core
npm install undici cheerio

# Supporting
npm install p-retry p-queue zod robots-parser tldts @mozilla/readability turndown pino

# Dev dependencies
npm install -D typescript tsdown vitest msw tsx @types/node
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| `undici` | `axios` | Use `axios` only if you require interceptor-heavy DX and do not care about transport-level tuning/per-call efficiency. |
| `cheerio` static-first extraction | Browser-first scraping via Playwright | Use Playwright fallback for JS-rendered pages that fail static extraction; do not make it default. |
| `tsdown` | `tsup` | Use `tsup` only in existing repos already standardized on it; for new SDKs, prefer `tsdown` due maintenance trajectory. |
| Single-provider Serper in v1 | Multi-provider routing from day one | Add multi-provider only after PMF and adapter stability; premature abstraction increases cost/complexity. |
| Optional Go hosted service later | Immediate hosted backend in v1 | Add backend only when client-only SDK hits latency/compliance limits you can measure. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Browser-first scraping as default (`playwright`/`puppeteer` on every URL) | High CPU/memory cost and slower p95; directly conflicts with "lowest cost per call" differentiation | Static-first pipeline (`undici` + `cheerio`) with selective browser fallback only |
| `tsup` for new greenfield SDKs | Package currently warns it is not actively maintained | `tsdown` |
| `jsdom` as default parser in fetch path | Heavier memory/runtime footprint for standard extraction workloads | `cheerio` first, `@mozilla/readability` only when needed |
| Multi-provider search abstraction in v1 | Expands test matrix and leaks provider-specific behavior into public API too early | Serper-only adapter boundary in v1 |
| Managed crawl platform as hard dependency (Firecrawl/Crawl4AI/etc.) | Reduces cost control and introduces external pricing/availability coupling | In-house scraper core with explicit optional integrations later |

## Stack Patterns by Variant

**If SDK-only (v1 launch):**
- Use Node + TypeScript package with direct Serper calls and in-process scraper.
- Because this minimizes infra spend and ships fastest for startup teams.

**If moving to hosted optimization service (later):**
- Use Go `1.25+` service for pooled HTTP/scraping workers, keep TypeScript SDK as API client.
- Because Go gives lower per-request runtime overhead and better central control of retries, caching, and concurrency budgets.

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `node@24` | `undici@7.x` | Undici 7.x aligns with Node 24 generation; strongest perf/control path. |
| `typescript@^5.7` | `zod@^4` | Zod 4 docs indicate TS 5.5+ support. |
| `vitest@4.x` | `vite@6/7/8` | Vitest 4 peer ranges include Vite 6/7/8. |
| `@mozilla/readability@0.6` | `jsdom@29` | Readability expects DOM input in Node; pair with jsdom only for fallback extraction flows. |
| `go@1.25+` | Optional hosted backend | Go 1.25 is a stable 2025 baseline for backend rollout timing. |

## Recommendation Confidence (Major Decisions)

| Recommendation | Confidence | Why |
|----------------|------------|-----|
| Static-first scraper core (`undici` + `cheerio`) | HIGH | Backed by official library docs and broad ecosystem usage; strongest cost/perf profile for this use case. |
| Node 24 LTS baseline | HIGH | Official Node LTS policy and active support status make this the safest default for production SDKs. |
| Serper-only in v1 | MEDIUM | Strong fit to product constraints and pricing claims, but vendor pricing/limits can change and should be monitored. |
| `tsdown` for new SDK bundling | MEDIUM | Supported by current tooling direction and tsup maintenance warning; still newer than long-established alternatives. |
| Optional Go service later (not day-one) | MEDIUM | Technically sound from runtime economics, but timing should be driven by measured bottlenecks post-v1. |

## Sources

- [Node.js Releases](https://nodejs.org/en/about/previous-releases) — LTS status and production guidance
- [TypeScript docs + release notes index](https://www.typescriptlang.org/docs/) — current TS release stream
- [Serper homepage](https://serper.dev/) — pricing/QPS/latency claims (official marketing source)
- [Undici npm package](https://www.npmjs.com/package/undici) — API/perf and Node compatibility notes
- [Cheerio npm package](https://www.npmjs.com/package/cheerio) — parser approach and adoption signal
- [Playwright intro docs](https://playwright.dev/docs/intro) — browser runtime requirements and intended usage
- [tsup npm package](https://www.npmjs.com/package/tsup) — maintenance warning
- [tsdown docs](https://tsdown.dev/) and [tsdown npm package](https://www.npmjs.com/package/tsdown) — recommended bundler path
- [p-retry npm package](https://www.npmjs.com/package/p-retry) — retry primitives/version
- [p-queue npm package](https://www.npmjs.com/package/p-queue) — concurrency primitives/version
- [Zod docs](https://zod.dev/) — Zod 4 status and TS requirements
- [robots-parser npm package](https://www.npmjs.com/package/robots-parser) — robots compliance helpers
- [tldts npm package](https://www.npmjs.com/package/tldts) — domain parsing strategy/performance
- [@mozilla/readability npm package](https://www.npmjs.com/package/@mozilla/readability) — extraction fallback behavior
- [turndown npm package](https://www.npmjs.com/package/turndown) — markdown conversion
- [Pino npm package](https://www.npmjs.com/package/pino) — low-overhead logging
- [Go release history](https://go.dev/doc/devel/release) — Go 1.25 release timeline for optional backend planning

---
*Stack research for: low-cost search + scrape SDK (TypeScript-first, Go optional)*
*Researched: 2026-03-15*
