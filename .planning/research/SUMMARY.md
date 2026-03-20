# Project Research Summary

**Project:** Parallel-like Web Extraction Agent
**Domain:** Web extraction agent for objective-driven evidence (deterministic excerpts + JS/PDF handling)
Researched: 2026-03-20
Confidence: MEDIUM

## Executive Summary
This project builds a tool-based web research agent that can fetch a single URL, extract “real deal” content (HTTP-first HTML, with JS rendering and PDF parsing fallbacks), and return evidence in a stable, evaluation-friendly format. Experts in this space typically separate concerns into a crawl pipeline behind a stable tool contract: bounded fetch and network controls, content-type routing, deterministic extraction/normalization, and (optionally) deterministic objective-driven excerpt selection with strict budgets.

Across the research, the recommended approach is to keep all messy web handling behind `web_crawl` so the agent always sees a normalized output contract. For v1, excerpt selection should be deterministic (default lexical ranking such as BM25 with stable tie-breaking) and set-output mode must be enforced at the tool/prompt/validation layers so DSQA “Fully Correct” scoring compares canonical sets rather than prose or unstable ordering.

The key risks are evaluation flakiness and contract drift: nondeterministic excerpt selection or a “prose leak” into set-output mode can silently break DSQA scoring, and JS/PDF fallbacks can fail in ways that look like success unless meta/status are surfaced. Mitigation is to enforce determinism in code, validate/parse set outputs with fail-closed behavior, use bounded Playwright rendering readiness logic, return structured fallback states, and add golden end-to-end tests that lock in excerpt normalization and set equivalence semantics.

## Key Findings

### Recommended Stack
The research recommends a Python-first extraction and tool runtime with deterministic local selection logic:

**Core technologies:**
- FastAPI — HTTP API tool surface (`/api/agent/run`) with ergonomic request/response modeling for tool orchestration.
- HTTPX — bounded fetch/retry control for predictable network behavior and cost limits.
- LangChain + LangGraph — agent/tool abstractions and a scalable “runtime graph” as orchestration grows.
- Playwright (Python) — JS-heavy “real deal” rendering with deterministic readiness checks and container-safe browser execution.
- PyMuPDF + OCRmyPDF — reliable PDF text extraction, with OCR as a targeted fallback when PDFs are scanned/image-based.
- trafilatura — high-quality HTML-to-text/markdown conversion for evidence extraction.
- rank-bm25 (+ optional reranking) — deterministic, cheap objective-driven excerpt ranking that avoids LLM variability in v1.

### Expected Features
The system’s “table stakes” are built around extraction modes, deterministic evidence formatting, and structured failure states:

**Must have (table stakes):**
- `excerpt` vs `full_content` extraction modes — users need either cheap evidence snippets or full extracted markdown.
- Objective-driven excerpting (`objective` + optional `search_queries[]`) — excerpts must align to downstream QA rather than be generic summaries.
- Deterministic set output mode — DSQA/evaluation requires stable arrays/sets (no prose, stable ordering, bounded sizes).
- Response contract + meta — minimum stable fields such as `url/title/publish_date/excerpts[]/full_content/meta.status` for downstream scoring and diagnostics.
- Structured fallback states — deterministic `meta.failure_reason` taxonomy when extraction fails or evidence is low-quality.
- JS/PDF “real deal” handling with safe fallbacks — degrade gracefully with explicit method transparency and failure buckets.
- Bounded budgets for v1 — hard caps on time/retries and excerpt count/character budget to prevent runaway cost.

**Should have (competitive):**
- Evidence-first excerpt fidelity — preserve quote text (or near reconstruction) so evidence is auditable.
- Deterministic excerpt ranking — objective/query signals combined with stable ranking and tie-breaking.
- Objective alignment signals in each excerpt — deterministic match scoring fields (e.g., matched terms/scores) to explain selection.
- Method transparency — expose `meta.extraction_method` / render usage flags for debugging and stratified eval.
- Full-content markdown with preserved links — stable formatting to support retrieval-augmented downstream steps.

**Defer (v2+):**
- Multi-URL fan-out orchestration — out of scope for v1; integration complexity and cost dominate.
- Deeper provenance/anchor mapping — after baseline excerpt quality is measured.
- Per-site extraction policy tuning and broader document structuring — once failure clusters and evaluation needs are known.

### Architecture Approach
The architecture should model `web_crawl` as a crawl pipeline behind a stable tool contract:
- fetch (bounded) → content-type router → render/extract (HTML/JS/PDF) → quality gates → optional deterministic excerpt selection → normalize to a response contract (`excerpts[]`, `full_content`, and structured `meta`).
Agent runtime should call canonical tools (`web_search`, `web_crawl`) and only return a final answer string; set-output determinism must be achieved via prompting + strict parsing/canonicalization + DSQA comparator logic rather than relying on natural-language model output.

**Major components:**
1. `web_crawl` tool adapter — validates input, orchestrates the pipeline, and returns success/error envelopes with stable schemas.
2. Crawl pipeline modules (`HttpFetchWorker`, `ContentTypeRouter`, extractors, quality gates) — converts bytes into normalized text/markdown with deterministic routing and bounded attempts.
3. Excerpt selection + normalization (`ExcerptSelector`, budget enforcement, response contract builder) — deterministic selection under hard budgets plus canonical schema shaping for DSQA.

### Critical Pitfalls
1. **Non-deterministic excerpt selection breaks DSQA set equivalence** — make excerpt selection deterministic in code (stable ranking + tie-breaking + hard budget enforcement) and normalize canonically before comparison.
2. **Output contract drift (prose leaks into set output mode)** — implement fail-closed parsing/validation for set/list mode; never forward invalid output to the evaluator.
3. **Fully Correct evaluation harness compares the wrong thing** — version and centralize the exact canonicalization + set comparison logic; add “golden prompt tests” and harness self-tests.
4. **JS “real deal” rendering fails silently or captures incomplete DOM** — use deterministic render readiness checks with capped render time; always record `meta.render_used` and surface failure reasons.
5. **PDF “real deal” extraction outputs empty/garbled text** — detect low/excessively empty extracted text early, gate excerpt selection on quality thresholds, and return structured PDF fallback reasons.

## Implications for Roadmap
Based on research, suggested phase structure:

### Phase 1: Local Runtime Foundation & Safety Gates
**Rationale:** Establish bounded network, containerized runtime assumptions, and baseline safety/contract infrastructure first; this reduces risk in later crawler/render/excerpt stages (including SSRF).
**Delivers:** Working compose/runtime scaffolding, environment validation, and baseline crawler safety (URL scheme validation, private-IP blocking, redirect limits) plus initial contract wiring.
**Addresses:** bounded budgets prerequisites for v1; safe crawler behavior to support JS/PDF later.
**Avoids:** SSRF/security pitfalls and unbounded network/render cost blowups.

### Phase 2: Search & Crawl Tool Capability (JS/PDF + Deterministic Excerpts)
**Rationale:** The crawl pipeline is the foundation for everything else; implement fetch→route→extract→quality→excerpt selection→normalize before integrating agent set-output mode and DSQA.
**Delivers:** `web_crawl` single-URL pipeline with content-type routing, HTML extraction (trafilatura), JS rendering (Playwright) with readiness logic, PDF extraction (PyMuPDF with OCRmyPDF fallback), objective-driven deterministic excerpting (BM25) under hard budgets, and stable response contracts/meta.
**Uses:** FastAPI/HTTPX stack, trafilatura, Playwright renderer, PyMuPDF+OCRmyPDF, rank-bm25, deterministic normalization.
**Implements:** modular pipeline components and `excerpts[]`/`full_content` contract shaping.
  
### Phase 3: Agent Execution Loop & API (Contract Stability + Set Output Parsing)
**Rationale:** After tool outputs are stable and deterministic, integrate them into the agent runtime and enforce set-output determinism at the boundary where `final_answer` is produced and parsed.
**Delivers:** Tool bindings (`web_search`, `web_crawl`), response contract -> prompt variable mapping, and strict “set output mode” parsing/validation (fail closed) so DSQA doesn’t see prose or invalid structures.
**Avoids:** output contract drift and schema mismatch by adding contract validation tests and prompt/parser alignment checks.

### Phase 4: Frontend Prompt Execution Surface (Operational UX for Evidence)
**Rationale:** Once API and contracts are stable, expose the prompt/execution surface for users/tests. This phase mostly builds on earlier determinism guarantees rather than reworking extraction.
**Delivers:** UI/server endpoints or prompt runner that passes `objective/search_queries` and presents deterministic outputs safely (including method/status meta for debugging).

### Phase 5: End-to-End Observability & Run History (DSQA Harness + Golden Tests)
**Rationale:** DSQA depends on exact canonicalization + set comparator semantics; harness correctness needs the highest confidence and must be protected against comparator bugs.
**Delivers:** DeepSearchQA/DSQA eval harness that parses canonical set output from `final_answer`, computes Fully Correct accuracy with ordering-insensitive comparison, logs safe structured metadata, and provides run history with traceable tool outputs.
**Avoids:** “Fully Correct compares wrong thing” and telemetry leaks by adding harness self-tests, canonicalization unit tests, and log payload caps.

### Phase Ordering Rationale
- Dependencies: the crawl pipeline and response contracts must exist before the agent prompt can transform tool outputs into deterministic set outputs.
- Architecture grouping: modularizing crawl pipeline (crawler/extractors/selector/normalizer) prevents monolithic branching and allows robust failure reasons for later DSQA stratification.
- Pitfall avoidance: Phase 2 is where determinism and budgets must be enforced; Phase 3 is where set parsing/validation prevents prose drift; Phase 5 is where comparator correctness and telemetry safety become critical.

### Research Flags
Phases likely needing deeper research:
- **Phase 2:** Deterministic “quality gates” thresholds (low-content detection), Playwright readiness signals, and OCR/threshold policy tuning are integration-heavy and need careful validation.
- **Phase 3:** Exact set-output parsing/canonicalization rules (JSON normalization, dedup, sorting) and schema/prompt mapping require precise alignment tests.
- **Phase 5:** DSQA comparator semantics, canonicalization function versioning, and golden end-to-end fixtures need dedicated verification.

Phases with standard patterns (skip research-phase):
- **Phase 1:** General bounded fetch/runtime scaffolding and SSRF mitigation are well-defined patterns with stable practices.
- **Phase 4:** Mostly wiring and UX over already-stable API/tool contracts; prioritize integration testing over new research.

## Confidence Assessment
| Area | Confidence | Notes |
|------|------------|-------|
| Stack | MEDIUM | Clear tech recommendations with official-source pointers, but some version pinning/compat specifics rely on repo alignment. |
| Features | MEDIUM | Features are well-motivated by eval needs and internal constraints; final contract field list needs implementation confirmation. |
| Architecture | MEDIUM | Architecture emphasizes modularity and stable tool contracts; it matches typical retrieval/evidence systems but implementation details still need validation. |
| Pitfalls | MEDIUM | Pitfall catalog is coherent and aligns with evaluation determinism risks; exact thresholds and readiness signals are still a gap to validate. |

**Overall confidence:** MEDIUM

### Gaps to Address
- Deterministic canonicalization rules for excerpts (whitespace, punctuation, unicode normalization) must be finalized and shared between generator and DSQA comparator.
- Playwright render readiness definition (“good enough” signal) and max render-time policies need empirical tuning on representative JS-heavy fixtures.
- PDF “low extracted text” thresholds and OCR gating need validation to avoid expensive OCR runs and to prevent empty/garbled excerpts.
- Cache key design (objective/search_queries/output mode/pipeline version) and cache invalidation policy should be locked to avoid wrong-excerpt reuse.
- Exact DSQA set comparator semantics (normalization + dedup + ordering-insensitive equality) must be versioned and tested with golden fixtures.

## Sources
### Primary (HIGH confidence)
- OWASP — SSRF guidance for URL validation, schemes, and private IP blocking.
- Playwright docs — loading/waiting and readiness behavior patterns.

### Secondary (MEDIUM confidence)
- Playwright (Python) — deterministic rendering support for extraction pipelines.
- PyMuPDF and OCRmyPDF — practical PDF text extraction and OCR fallback behaviors.
- rank-bm25 — deterministic lexical scoring for objective-aligned excerpt selection.

### Tertiary (LOW confidence)
- Specific threshold values (quality gates, excerpt char budgets) — need empirical tuning and golden fixture validation.
- Sentence-transformers reranking determinism and budget effects — optional v2 path; not fully specified in research.

---
*Research completed: 2026-03-20*
*Ready for roadmap: yes*

