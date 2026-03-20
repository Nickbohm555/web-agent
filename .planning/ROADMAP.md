# Roadmap: Parallel-like Web Extraction Agent

## Overview
This v1 builds a single-URL web evidence pipeline that can extract reliable content from messy pages by routing to the right extraction method (HTTP HTML, JS render, or PDF parsing/OCR). It then enforces deterministic, arrays-only outputs so offline DeepSearchQA evaluation can compute Fully Correct set equivalence.

## Phases
**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work

- [ ] **Phase 1: Extraction Pipeline + Unified Evidence Contract** - Deterministic JS/PDF handling, objective excerpts/full content, and a stable per-URL response contract
- [ ] **Phase 2: Deterministic Set Output Mode** - Fail-closed parsing so agent `final_answer` becomes a deterministic arrays-only structure
- [ ] **Phase 3: Offline DeepSearchQA Eval Harness** - End-to-end DSQA runs with strict canonical set equivalence comparison

## Phase Details

### Phase 1: Extraction Pipeline + Unified Evidence Contract
**Goal**: Users can fetch a single URL and reliably get deterministic evidence (objective excerpts and/or full markdown) with JS/PDF real handling and structured meta for both success and failure.
**Depends on**: Nothing (first phase)
**Requirements**: EXTR-01, EXTR-02, EXTR-03, EXTR-04, REND-01, REND-02, REND-03, REND-04, CONT-01, CONT-02
**Success Criteria** (what must be TRUE):
  1. User can request `excerpt` mode and receive objective-driven `excerpts[]` with deterministic ordering, enforcing the v1 budget (<= 3 excerpts/url and <= 300 chars per excerpt).
  2. User can request `full_content` mode and receive full extracted markdown in `full_content` with preserved links.
  3. JS-heavy pages are rendered (not just raw HTML) and extraction quality degrades gracefully with stable `meta.extraction_method` and a populated `meta.status`.
  4. PDFs are extracted via real text extraction, triggering an OCR fallback for scanned/low-text PDFs when needed, with `meta.extraction_method` and structured fallback reasons surfaced on failure/degradation.
  5. The tool always returns a unified per-URL response contract with `url`, `title`, `publish_date`, `excerpts[]`, `full_content`, and `meta` populated on both success and failure (no silent empties without failure reason).
**Plans**: 3 plans

Plans:
- [ ] 01-01: Implement JS/PDF extraction pipeline + fallback reasons
- [ ] 01-02: Implement deterministic objective-driven excerpt selection + budgets
- [ ] 01-03: Finalize unified response contract + meta population on failure

### Phase 2: Deterministic Set Output Mode
**Goal**: Users (and the DSQA harness) can rely on agent `final_answer` to be a deterministic arrays-only structure that can be parsed canonically, or the run fails fail-closed with a stable error category/message.
**Depends on**: Phase 1
**Requirements**: OUT-01, OUT-02
**Success Criteria** (what must be TRUE):
  1. With set output mode enabled, user-visible agent `final_answer` is an arrays-only structure (no prose) and can be normalized into the strict representation required by evaluation.
  2. If set-output parsing/normalization cannot be performed deterministically, the run fails with a stable error category/message (no “best effort” incorrect output).
**Plans**: 1 plan

Plans:
- [ ] 02-01: Add fail-closed set output parsing + canonical normalization

### Phase 3: Offline DeepSearchQA Eval Harness
**Goal**: Users can run an offline DeepSearchQA evaluation that executes the agent end-to-end per prompt and computes Fully Correct exact set equivalence using strict canonicalization (ordering-insensitive).
**Depends on**: Phase 2
**Requirements**: EVAL-01, EVAL-02
**Success Criteria** (what must be TRUE):
  1. DSQA harness runs offline per prompt and reports an accuracy metric based on Fully Correct exact set equivalence.
  2. The harness forces agent outputs into a strict list/set representation so ordering differences do not affect “equal sets” comparison (canonicalization aligns with DSQA semantics).
**Plans**: 1 plan

Plans:
- [ ] 03-01: Implement DSQA end-to-end harness + canonical set comparator

## Progress
**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1 - Extraction Pipeline + Unified Evidence Contract | 0/3 | Not started | - |
| 2 - Deterministic Set Output Mode | 0/1 | Not started | - |
| 3 - Offline DeepSearchQA Eval Harness | 0/1 | Not started | - |

