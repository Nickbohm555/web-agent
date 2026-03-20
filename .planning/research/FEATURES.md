# Feature Research

**Domain:** Parallel-like Web Extraction Agent (single-URL tool mode)
**Researched:** 2026-03-20
**Confidence:** MEDIUM

## Feature Landscape

### Table Stakes (Users Expect These)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Extraction modes (`excerpt` vs `full_content`) | Users need either cheap evidence snippets or full retrievable content | Medium | Modes must share the same underlying extraction pipeline and contracts |
| Objective-driven excerpting (`objective`, optional `search_queries[]`) | Excerpts should be targeted for downstream QA, not generic summaries | High | Must support objective-driven selection/ranking under a per-page excerpt budget |
| Deterministic set output mode | Evaluation and downstream tooling require stable, parseable outputs (arrays, not prose) | Medium | Stable ordering + bounded array lengths are required for deterministic scoring |
| Response contract + meta | Consumers must know what was fetched/extracted and why failures happened | Low/Med | At minimum: `url`, `title`, `publish_date`, `excerpts[]`, `full_content` (optional), and `meta.status` |
| Structured fallback states | Pages fail in predictable ways (empty/low-quality/unsupported type/timeouts) | Medium | `meta.failure_reason` (or equivalent) must be machine-readable and stable across runs |
| JS/PDF “real deal” handling with safe fallbacks | Many web sources are JS-rendered or PDF-first; extraction must degrade gracefully | High | JS via a render step; PDF via text extraction. If unavailable, return structured failure reasons and partial evidence when possible |
| Bounded budgets for v1 excerpting | Cost/budget constraints prevent runaway extraction and make behavior predictable | Medium | Bounded timeouts/retries (network + render) and bounded per-page excerpt size (count + chars) |

### Differentiators (Competitive Advantage)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Evidence-first excerpts (quote fidelity) | Downstream answers can cite exact passages instead of relying on paraphrase | High | Excerpts should preserve quote text (or very close reconstruction) and include trace metadata (e.g., `evidence_id`, `source` hints) |
| Deterministic excerpt ranking | Objective-driven selection is reproducible for eval and regression tests | High | Use deterministic heuristics plus `search_queries[]` as ranking signal; avoid random sampling |
| Objective alignment signals in each excerpt | Improves both transparency and scoring (e.g., why an excerpt was chosen) | Medium | Include fields like `objective_terms_matched` / `objective_match_score` (deterministic) |
| Method transparency (render vs HTML vs PDF) | Makes quality issues diagnosable and lets eval separate “hard pages” from “bad extraction” | Medium | `meta.extraction_method` and attempt flags (e.g., `render_attempted: true/false`) |
| Full-content markdown with preserved links | Supports retrieval-augmented downstream steps while keeping formatting consistent | Medium | Links should map to original URLs; output should be stable given the same inputs |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Natural-language prose output in excerpt mode (when deterministic is required) | Easier to read manually | Breaks DSQA/eval parsing, increases nondeterminism, and loses evidence structure | “Set output mode”: arrays-only excerpt objects + stable schema |
| Unbounded excerpts / variable-length outputs | “More context is better” | Makes cost unpredictable and destabilizes evaluation | Enforce per-page excerpt count and per-excerpt char budget |
| Silent failures (empty excerpts/full_content without meta) | Less noise | Evaluations can’t distinguish “correctly empty” vs “broken extraction”, causing misleading accuracy | Always populate `meta.status` and a stable failure reason |
| Over-summarization that removes traceability | Looks good to humans | QA needs citations; summarization can hallucinate or drift from source quotes | Evidence-first excerpts + extract raw text/quotes with trace metadata |
| Multi-URL fan-out in v1 | Higher throughput | Scope creep: orchestration + retries + aggregation dominate complexity and cost | Keep v1 single-URL tool mode; multi-URL orchestration is later |
| Logging raw page bodies/provider internals | Easier debugging | Privacy/safety risk and possible secrets leakage; increases payload size | Keep logs structured and safe; expose sanitized `meta` only |

## Feature Dependencies

```
[Rendering/Extraction Method Selection]
    └──requires──> [Page text layer (HTML -> text, JS -> rendered text, PDF -> PDF text)]
                       ├──requires──> [Content-type detection + attempt policy]
                       ├──enhances──> [JS render fidelity] 
                       └──enhances──> [PDF text extraction]

[Excerpting (objective-driven)]
    └──requires──> [Page text layer]
    └──requires──> [Objective + ranking signal (objective, search_queries[])]
    └──requires──> [Bounded excerpt budget]

[Set Output Mode]
    └──requires──> [Excerpting (objective-driven)] (for excerpt arrays)
    └──requires──> [Stable excerpt schema + deterministic ordering]

[Full Content Mode]
    └──requires──> [Page text layer]
    └──requires──> [Safe markdown rendering rules]

[Response Contract + Meta]
    ├──requires──> [Rendering/Extraction Method Selection] (to label method)
    └──requires──> [Failure taxonomy] (to label errors deterministically)

[DSQA Eval Harness]
    └──requires──> [Set Output Mode] (machine-parseable evidence)
    └──requires──> [Response contract + meta] (to score/segment failures)
    └──requires──> [Deterministic ranking] (for regression stability)
    └──requires──> [Objective input handling] (to map prompts to excerpt selection)
```

### Dependency Notes

- **[Excerpting (objective-driven)] requires [Page text layer]:** excerpt selection must operate on the same canonical extracted text; JS/PDF pages must be rendered/extracted before selection.
- **[Set Output Mode] requires [Deterministic ordering + bounded budgets]:** stable arrays and stable ranking are prerequisites for eval reproducibility.
- **[Response contract + meta] requires [Failure taxonomy]:** DSQA needs to distinguish “extraction succeeded but low evidence” from “extraction failed due to unsupported type/timeouts”.
- **[DSQA Eval Harness] requires [Set Output Mode] and [meta]:** scoring depends on deterministic evidence objects and meta that can be used for diagnostics or stratified evaluation.

## MVP Definition

### Launch With (v1)

Minimum viable product — what's needed to validate the concept.

- [ ] `excerpt` mode with objective-driven excerpt selection (bounded `excerpts[]`, deterministic ordering)
- [ ] `full_content` mode returning extracted markdown (links preserved) for follow-up QA/retrieval
- [ ] Unified response contract including `url/title/publish_date/excerpts/full_content/meta`
- [ ] JS/PDF “real deal” handling with structured fallbacks (`meta.status` + stable failure reasons)
- [ ] `set output mode` (arrays-only) so DSQA can parse evidence deterministically
- [ ] DSQA eval harness: end-to-end prompt->extract->score loop that computes Fully Correct accuracy

### Add After Validation (v1.x)

- [ ] Deeper provenance (e.g., stable fragment/anchor mapping for excerpts) once evidence quality baselines are known
- [ ] Per-site extraction policies (tighter attempt policy tuning) after you see recurring failure clusters

### Future Consideration (v2+)

- [ ] Multi-URL extraction orchestrator and parallel fan-out (if/when v1 proves value)
- [ ] Higher-level document structuring (sections, tables) once evaluation demands it

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Objective-driven excerpting (`excerpt` mode) | HIGH | HIGH | P1 |
| Deterministic set output mode | HIGH | MEDIUM | P1 |
| Response contract + meta | HIGH | MEDIUM | P1 |
| JS/PDF real handling with fallbacks | HIGH | HIGH | P1 |
| Full content mode | MEDIUM | MEDIUM | P2 |
| DSQA eval harness | HIGH | MEDIUM/HIGH | P1 |

**Priority key:**
- P1: Must have for launch
- P2: Should have, add when possible
- P3: Nice to have, future consideration

## Competitor Feature Analysis

| Feature | Competitor A | Competitor B | Our Approach |
|---------|--------------|--------------|--------------|
| Objective-driven excerpts | Varies; often summary-first | Varies; often extraction-first | Deterministic evidence objects bounded by budget |
| Deterministic set outputs | Often not eval-friendly | Often not eval-friendly | Set-output schema designed for DSQA parsing |
| JS/PDF real handling | Partial; fallbacks common | Partial; fallbacks common | Explicit method transparency + structured fallback taxonomy |

## Sources

- Internal project constraints (from `.planning/PROJECT.md`)
- General “eval-friendly evidence” patterns used for retrieval/QAP systems (needs follow-up competitor validation if desired)

---
*Feature research for: Parallel-like Web Extraction Agent*
*Researched: 2026-03-20*

