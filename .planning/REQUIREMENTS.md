# Requirements: Parallel-like Web Extraction Agent

**Defined:** 2026-03-20
**Core Value:** Return accurate, high-signal web evidence in a stable format even when pages are messy (bad HTML, low text, redirects, JS/PDF).

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Extraction Modes & Objective Excerpts

- [ ] **EXTR-01**: User can request `excerpt` mode and receive objective-driven excerpts (deterministic, bounded, stable ordering)
- [ ] **EXTR-02**: User can request `full_content` mode and receive full extracted markdown content (links preserved)
- [ ] **EXTR-03**: Excerpt budget is enforced in v1 (<= 3 excerpts/url; <= 300 chars per excerpt)
- [ ] **EXTR-04**: `objective` is the primary signal and `search_queries[]` is the secondary ranking/select signal for excerpts (without changing crawl strategy)

### JS/PDF Real Handling & Fallbacks

- [ ] **REND-01**: JS-heavy pages are handled via a real render step (Playwright) and the extracted readable output is fed into excerpting/full content
- [ ] **REND-02**: PDFs are handled via real text extraction (PyMuPDF) with OCR fallback for scanned/low-text PDFs
- [ ] **REND-03**: Content-type detection + attempt policy chooses the appropriate extraction method (HTML vs rendered HTML vs PDF)
- [ ] **REND-04**: When extraction fails or degrades, the tool returns structured fallback reasons and stable `meta.status` / `meta.extraction_method` fields

### Unified Response Contract & Meta

- [ ] **CONT-01**: Tool output follows a unified per-URL response contract including: `url`, `title`, `publish_date`, `excerpts[]`, `full_content`, and `meta`
- [ ] **CONT-02**: `meta` is populated on both success and failure and is machine-readable (no silent empties without failure reason)

### Deterministic Set Output Mode & Evaluation Parsing

- [ ] **OUT-01**: `set output mode` is supported so the agent’s `final_answer` is a deterministic arrays-only structure (no prose)
- [ ] **OUT-02**: Output parsing/normalization for set mode is fail-closed (if it can’t parse deterministically, the run fails with a stable error category/message)

### DeepSearchQA (DSQA) Eval Harness

- [ ] **EVAL-01**: Add an offline DSQA evaluation harness that runs the agent end-to-end per prompt and computes Fully Correct exact set equivalence
- [ ] **EVAL-02**: The harness forces agent outputs into a strict list/set representation for comparison (canonicalization matches DSQA semantics)

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Evidence Fidelity & Provenance

- **PROV-01**: Add deeper provenance for excerpts (stable evidence anchors/fragment mapping) once baseline evidence quality is established
- **PROV-02**: Add per-site extraction policies (tuned attempt policies and thresholds after observing failure clusters)

### Throughput / Orchestration

- **ORCH-01**: Multi-URL extract orchestrator / parallel fan-out in v2 (v1 stays single-URL tool mode)

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Multi-URL fan-out orchestration in v1 | Higher complexity and cost; defer until extraction quality is validated |
| Prose/non-deterministic excerpt outputs in excerpt mode | Breaks DSQA parsing and makes regressions hard |
| Natural-language “helpful summaries” as the primary excerpt representation | Removes traceability and increases nondeterminism |
| Unbounded excerpts / variable-length outputs | Makes costs unpredictable and destabilizes evaluation |
| Logging raw page bodies/provider internals by default | Privacy/safety risk and payload bloat |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| EXTR-01 | Phase 1 | Pending |
| EXTR-02 | Phase 1 | Pending |
| EXTR-03 | Phase 1 | Pending |
| EXTR-04 | Phase 1 | Pending |
| REND-01 | Phase 1 | Pending |
| REND-02 | Phase 1 | Pending |
| REND-03 | Phase 1 | Pending |
| REND-04 | Phase 1 | Pending |
| CONT-01 | Phase 1 | Pending |
| CONT-02 | Phase 1 | Pending |
| OUT-01 | Phase 2 | Pending |
| OUT-02 | Phase 2 | Pending |
| EVAL-01 | Phase 3 | Pending |
| EVAL-02 | Phase 3 | Pending |

**Coverage:**

- v1 requirements: 14 total
- Mapped to phases: 14
- Unmapped: 0 ✅

---
*Requirements defined: 2026-03-20*
*Last updated: 2026-03-20 after v1 scoping*

