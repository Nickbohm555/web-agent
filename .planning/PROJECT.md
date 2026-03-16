# Web Search SDK

## What This Is

This project is an SDK-first web search toolkit for startup teams building agentic products. It combines a Serper-backed search provider with an in-house web scraper so agents can move from search snippets to full-page context quickly and cheaply. The initial product focus is exposing two reliable primitives, `search(...)` and `fetch(...)`, with a TypeScript SDK as the primary developer surface.

## Core Value

Deliver the lowest-cost path to production-grade search plus page retrieval context for agent systems without sacrificing practical developer usability.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

(None yet — ship to validate)

### Active

<!-- Current scope. Building toward these. -->

- [ ] Agent developers can call a `search(query, options)` tool that returns relevant, normalized search results using Serper.
- [ ] Agent developers can call a `fetch(url, options)` tool that returns clean, parseable page content from an in-house scraper.
- [ ] The system is optimized for low cost per call and transparent usage tradeoffs suitable for startup-scale budgets.
- [ ] The initial implementation ships with a TypeScript SDK as the primary integration surface.
- [ ] The architecture leaves room for an optional Go hosted service later if direct backend control is needed for speed/cost optimization.
- [ ] The initial implementation targets US + English usage patterns.

### Out of Scope

<!-- Explicit boundaries. Includes reasoning to prevent re-adding. -->

- Multiple search providers beyond Serper in v1 — single-provider focus reduces complexity and supports faster cost optimization.
- MCP-first productization — SDK-first delivery is prioritized to match the target audience and integration workflow.
- Enterprise multi-tenant/compliance platform features — not required for first-party validation in startup environments.

## Context

The project is inspired by Onyx's split between search providers and web scraping, where search snippets alone are not sufficient for complete answer context. The key user pain to address is high API cost for search and scraping workflows used in agent systems. The initial success bar is internal production confidence: the creator can depend on this stack in their own products before broader commercialization.

## Constraints

- **Provider**: Serper is the only search provider in v1 — cost and implementation focus.
- **Architecture**: TypeScript SDK first, optional Go service later — keeps v1 focused while preserving a path to hosted optimization.
- **Interface**: Two primary tools (`search`, `fetch`) — keep API surface focused and composable.
- **Market**: Startup teams first — optimize for practical integration and cost sensitivity.
- **Region/Language**: US + English first — avoid premature global complexity.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| SDK-first over MCP-first | Faster integration for target startup teams using app-level clients | — Pending |
| Expose two primitives: `search` and `fetch` | Clear separation of concerns mirrors retrieval pipeline needs | — Pending |
| Use Serper for search provider | Cost-effective baseline and quick path to implementation | — Pending |
| Build in-house scraper | Control over query privacy and per-call cost profile | — Pending |
| Prioritize lowest cost in v1 | Primary differentiation goal versus existing search tools | — Pending |
| TypeScript SDK is the public v1 surface | Minimizes time to developer adoption and keeps integration simple | — Pending |
| Go service is optional and deferred | Build only if hosted backend control is needed for better speed/cost economics | — Pending |

---
*Last updated: 2026-03-15 after architecture clarification*
