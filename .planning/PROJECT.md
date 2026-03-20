# Parallel-like Web Extraction Agent

## What This Is

This project builds a web research agent that can fetch a page, extract its main content, and return evidence in a Parallel-like, tool-friendly format (full content or objective-driven excerpts).
It’s for building reliable “web evidence” for downstream question answering/evaluation, using bounded network retrieval plus consistent output contracts.

## Core Value

Return accurate, high-signal web evidence in a stable format even when pages are messy (bad HTML, low text, redirects, JS/PDF).

## Requirements

### Validated

- ✓ `POST /api/agent/run` endpoint exists and runs the agent runtime
- ✓ Canonical backend tools are bound as `web_search` and `web_crawl`
- ✓ `web_search` uses Serper (`SERPER_API_KEY`) and normalizes results
- ✓ `web_crawl` is HTTP-first with retries and extracts readable content via `trafilatura`, returning structured fallback reasons on failure

### Active

- [ ] Extend `web_crawl` (single URL) to support `objective?` and `search_queries?` for objective-driven excerpt selection
- [ ] Implement `full_content` mode: return the extracted page content as full markdown (links preserved)
- [ ] Implement excerpt mode: select a small set of high-signal excerpts under a “cheap” budget
- [ ] Add real JS/PDF handling with structured fallbacks when extraction cannot be performed
- [ ] Upgrade the extraction response contract to include: `url`, `title`, `publish_date`, `excerpts[]`, `full_content`, and `meta` (status + fetch/extraction details)
- [ ] Add set output mode for deterministic arrays (no prose)
- [ ] Add DeepSearchQA eval harness to run prompts end-to-end and compute Fully Correct accuracy

### Out of Scope

- [Exclusion] Multi-URL extract orchestrator / new “extract endpoint” (no separate fan-out orchestration in v1)
- [Exclusion] Changing the existing canonical tool binding names (`web_search`, `web_crawl`) in the agent runtime
- [Exclusion] Logging raw page bodies or provider internals by default (keep outputs and telemetry safe)

## Context

- Repo is a FastAPI + LangChain backend with two canonical tools: `web_search` and `web_crawl`.
- Current crawl/extraction is HTTP-first and uses `trafilatura`; it supports fallback states like `unsupported-content-type` and `low-content-quality`.
- The agent runtime currently returns only a final answer string to the API, so tool outputs must be transformed into deterministic final-answer formats via prompting.
- “Parallel-like” target behavior is captured in `features.md` (full content, objective-driven excerpts, response contract, set output mode, and DSQA evaluation).

## Constraints

- **Cost/Budget**: excerpt selection in v1 must be “cheap” (small per-page excerpt budget).
- **Bounded Network**: retrieval must keep timeouts and retry counts bounded to prevent runaway cost (current crawl uses bounded timeouts/retries).
- **Safety/Privacy**: never log secrets and do not include raw provider internals in user-visible output.
- **Compatibility**: keep `web_search`/`web_crawl` tool names stable; extend inputs/outputs in a backwards-compatible way where possible.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Implement “Parallel-like” excerpt/objective behavior by extending `web_crawl` for a single URL (no multi-URL orchestrator in v1) | Keeps v1 small and aligns with existing runtime/tool plumbing | — Pending |
| Use `search_queries[]` as ranking/select signal for excerpts only (do not alter crawl strategy) | Lower complexity and preserves HTTP-first policy | — Pending |
| JS/PDF real-deal stack for v1: Playwright for JS rendering + PyMuPDF for PDF text | Matches “real deal” requirement for messy content | — Pending |
| Excerpt budget for v1: small (<= 3 excerpts per URL, <= 300 chars each) | Satisfies “cheap, idk” constraint and keeps outputs deterministic | — Pending |
| DSQA harness is part of v1 scope (end-to-end evaluation + Fully Correct accuracy) | Makes extraction quality measurable | — Pending |

---
*Last updated: 2026-03-20 after initial project setup*

