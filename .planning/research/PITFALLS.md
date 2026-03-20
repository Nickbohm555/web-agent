# Pitfalls Research

**Domain:** Web extraction agents (objective-driven excerpts + deterministic set outputs, incl. JS/PDF + DSQA eval)
**Researched:** 2026-03-20
**Confidence:** MEDIUM

## Critical Pitfalls

### Pitfall 1: Non-deterministic excerpt selection breaks DSQA "set equivalence"

**What goes wrong:**
Excerpt sets (and/or the final "set output" items) vary run-to-run for the same `(url, objective, search_queries, excerpt_budget)` even when nothing else changes.

**Why it happens:**
- Excerpt selection is model-generated (or depends on nondeterministic ranking) instead of deterministic scoring + stable ordering.
- LLM decoding randomness (temperature, top_p, nondeterministic tool retries) leaks into outputs.
- Ordering is not canonical (different but equivalent selections are treated as different).
- Normalization/canonicalization (case, whitespace, punctuation, unicode) differs between generation and evaluation.

**How to avoid:**
- Make excerpt selection deterministic in code whenever possible (deterministic ranking, stable sort keys, fixed budget enforcement).
- If an LLM is used for selection, constrain decoding (temperature=0, fixed system prompt), and still force canonical sorting + strict output validation.
- Normalize excerpts before returning and use the same normalization in the DSQA comparator.
- Treat "budget" as a first-class constraint (hard cap on number of excerpts and chars/tokens per excerpt).

**Warning signs:**
- DSQA Fully Correct accuracy fluctuates significantly across repeated runs on the same dataset.
- Log comparisons show different `excerpts[]` for identical inputs.
- "Almost right" results are marked wrong because the evaluation expects exact set items.

**Phase to address:**
Phase 02-search-and-crawl-tool-capability; Phase 03-agent-execution-loop-and-api

---

### Pitfall 2: Output contract drift (prose leaks into "set output" mode)

**What goes wrong:**
The agent's final response is expected to be a strict deterministic set/list, but returns prose, extra commentary, or a non-parseable structure. DSQA then fails due to formatting or semantic mismatch.

**Why it happens:**
- Prompting relies on "the model will comply" rather than hard validation and rejection/retry.
- Set/list semantics are not enforced (e.g., duplicates not removed, ordering not canonical, items not normalized).
- Tool outputs are transformed into natural language rather than a strict `output_format="set"` contract.

**How to avoid:**
- Implement an output validator/parser for the set/list mode and fail closed (do not send invalid output to eval).
- Keep set outputs schema-driven (structured JSON or strict line-separated items) with deterministic canonicalization.
- Put the "no prose" constraint in the system/developer prompt and verify it in automated contract tests.

**Warning signs:**
- DSQA harness frequently shows parse errors or low accuracy tied to formatting rather than content.
- Manual inspection finds explanations mixed with the intended set items.

**Phase to address:**
Phase 03-agent-execution-loop-and-api; Phase 04-frontend-prompt-execution-surface

---

### Pitfall 3: Fully Correct evaluation harness compares the wrong thing

**What goes wrong:**
The DSQA harness reports low/high "Fully Correct accuracy" due to comparator bugs, not because the extractor is actually wrong.

**Why it happens:**
- The harness compares ordered arrays instead of sets (or dedups at the wrong stage).
- Canonicalization differs (case/whitespace/url normalization/Unicode normalization differs).
- The harness uses different constraints than production (e.g., allowing full content in eval when production uses excerpts).
- The harness feeds the wrong prompt variables or uses stale prompt templates.

**How to avoid:**
- Define and version the exact canonicalization function used for generation and evaluation.
- Compare mathematical sets with explicit dedup semantics and ordering-insensitive logic.
- Add "golden prompt tests" that ensure the harness itself is stable (same input => same set comparison outcome).
- Run end-to-end "agent output -> DSQA set comparator -> Fully Correct" tests before trusting scores.

**Warning signs:**
- Accuracy changes when you change formatting (whitespace/casing) but not the underlying items.
- Discrepancies between human-labeled correctness and harness results.
- Test-suite passes but DSQA metrics fail on the same sample after refactors.

**Phase to address:**
Phase 05-end-to-end-observability-and-run-history

---

### Pitfall 4: JS "real deal" rendering fails silently or captures incomplete DOM

**What goes wrong:**
For JS-heavy pages, Playwright-based rendering returns content that is missing the key information because extraction happens before the page finishes rendering (or never becomes "ready" in a deterministic way).

**Why it happens:**
- "Network idle" assumptions break on SPAs (long-polling/websockets never settle).
- Waiting heuristics are too generic (e.g., fixed delays) so timing varies across runs/machines.
- Fallback status is not surfaced (render fails, but the pipeline still treats it as success).
- Render_used is not recorded, so you cannot debug why excerpts changed.

**How to avoid:**
- Implement deterministic render readiness logic: cap render time, wait for specific stable signals (selectors, content presence), and use fallback states explicitly.
- Record `meta.render_used`, `meta.status`, and failure reasons in the extraction response contract.
- If JS render cannot reach a "good enough" signal, return a structured fallback and ensure excerpt selection handles that state deterministically.

**Warning signs:**
- Many JS-heavy pages produce low-quality excerpts while `render_used=false` (or is not reported).
- Re-running the same URL changes excerpt contents disproportionately.
- "Unsupported" vs "low-quality" vs "render failed" buckets are inconsistent.

**Phase to address:**
Phase 02-search-and-crawl-tool-capability

---

### Pitfall 5: PDF "real deal" extraction outputs empty/garbled text (scanned/encrypted/complex PDFs)

**What goes wrong:**
PDF handling claims success but produces no meaningful text (or unpredictable gibberish). Excerpt selection then becomes guesswork and set outputs become unstable or wrong.

**Why it happens:**
- PDFs are image/scanned and text extraction returns almost nothing (no OCR path, or OCR out of scope).
- Encrypted/password-protected PDFs fail extraction.
- Very large PDFs hit resource limits or timeouts.
- Different environments produce different text ordering/line breaks (affecting deterministic selection).

**How to avoid:**
- Detect extraction quality early (e.g., minimal text length) and return structured fallback reasons (e.g., `scanned-pdf-unsupported`, `encrypted-pdf`, `pdf-extraction-failed`).
- Enforce deterministic PDF extraction settings (page limits, deterministic ordering).
- If OCR is introduced later, ensure deterministic OCR configuration and treat OCR as a distinct pipeline stage with metadata.

**Warning signs:**
- High rate of PDFs with `excerpts[]` derived from near-empty text.
- "publish_date"/key entities missing systematically for PDFs.
- Excerpt selection still runs and produces items even when the extracted text quality is below threshold.

**Phase to address:**
Phase 02-search-and-crawl-tool-capability

---

## Moderate Pitfalls

### Pitfall 6: Budget enforcement is partial (cost blowups + truncation-induced nondeterminism)

**What goes wrong:**
Excerpt selection is "cheap" conceptually, but actual implementation lets full content bleed into ranking/selection, causing variable truncation and inconsistent outputs.

**Why it happens:**
- Budgets are enforced only at the UI layer, not inside the extraction and serialization pipeline.
- Char/token caps differ between extraction vs eval harness.
- The response contract truncates inconsistently (different segments per run).

**How to avoid:**
- Enforce excerpt budget at the extraction-to-excerpt boundary with hard caps (count and per-excerpt length).
- Track budget usage in `meta` (e.g., `meta.excerpt_budget_chars_used`).
- Ensure the DSQA harness uses the same excerpt truncation logic as production.

**Warning signs:**
- DSQA runtime cost spikes even when excerpt budgets are configured.
- "Identical URL" produces different excerpts due to different truncation boundaries.

**Phase to address:**
Phase 02-search-and-crawl-tool-capability; Phase 05-end-to-end-observability-and-run-history

---

### Pitfall 7: Cache key mistakes return the wrong excerpts for a different objective

**What goes wrong:**
Caching uses only `url` but ignores objective/search_queries/output mode. Different objectives receive identical excerpt sets.

**Why it happens:**
- Cache key is incomplete.
- Pipeline versioning is missing, so old excerpt formats are reused after changes.

**How to avoid:**
- Include objective, search_queries, excerpt_budget, and output mode in cache keys.
- Version the extraction pipeline and store pipeline version in `meta` so old cache entries are invalidated.

**Warning signs:**
- Changing objective yields unchanged excerpts.
- After code changes, evaluation results do not improve even though logic changed.

**Phase to address:**
Phase 02-search-and-crawl-tool-capability

---

### Pitfall 8: Boilerplate/unstable HTML normalization contaminates excerpts

**What goes wrong:**
Excerpt content contains navigation, cookie banners, repeated headers/footers, or unstable DOM sections that shift across runs, causing deterministic selection to become noisy.

**Why it happens:**
- Extraction normalization is not canonical (whitespace, line breaks, link rendering).
- Boilerplate removal is inconsistent across content types (HTML vs JS vs PDF-converted markdown).

**How to avoid:**
- Define a canonical markdown/text normalization pipeline used for all sources.
- Apply stable boilerplate removal rules and test them with golden fixtures across multiple page types.
- Ensure link preservation is consistent so excerpts include stable evidence anchors.

**Warning signs:**
- Excerpts frequently include repeated "chrome" text rather than objective-relevant evidence.
- Excerpts differ more than expected between render modes (HTTP-only vs JS render).

**Phase to address:**
Phase 02-search-and-crawl-tool-capability

---

### Pitfall 9: Tool/runtime schema mismatch (meta/excerpts contract changes without prompt updates)

**What goes wrong:**
`web_crawl` response contract evolves (new fields, renamed fields, changed types) but the agent prompts and DSQA harness still expect the old shape.

**Why it happens:**
- No schema validation between tool outputs and agent prompt variables.
- No versioning or backward-compatible adapters.

**How to avoid:**
- Validate tool outputs against a schema at runtime (and in tests).
- Add integration tests: "tool output contract -> prompt variable mapping -> set output parse".
- Version response contracts and keep compatibility adapters until prompts/harnesses are updated.

**Warning signs:**
- Frequent missing fields in `meta` or `excerpts[]`.
- Evaluation harness shows systemic failures after seemingly unrelated refactors.

**Phase to address:**
Phase 03-agent-execution-loop-and-api; Phase 05-end-to-end-observability-and-run-history

---

## Minor Pitfalls

### Pitfall 10: SSRF and unsafe URL handling in fetch/crawl

**What goes wrong:**
The crawler fetches internal network addresses, metadata endpoints, or unsupported schemes, creating security risk.

**Why it happens:**
- URL validation is minimal or missing.
- Redirect handling allows "escaping" the intended domain/range.

**How to avoid:**
- Block private IP ranges and link-local/metadata IPs.
- Restrict schemes (http/https only).
- Enforce redirect limits and validate the final resolved destination host.

**Warning signs:**
- Unexpected outbound requests to RFC1918, link-local, or metadata IPs.
- Security scanning finds SSRF-class issues.

**Phase to address:**
Phase 01-local-runtime-foundation; Phase 02-search-and-crawl-tool-capability

---

### Pitfall 11: Telemetry/DSQA logs leak sensitive content or exceed budgets

**What goes wrong:**
Logs store full extracted bodies, provider internals, or large payloads, increasing privacy and operational risk.

**Why it happens:**
- Debug logging accidentally prints full text or raw provider responses.
- Eval harness dumps large objects by default.

**How to avoid:**
- Redact or cap logged payload sizes.
- Prefer hashes, truncated excerpts, and stable identifiers (url, run_id, status) over raw bodies.

**Warning signs:**
- Log sizes balloon; PII/secret-like strings appear in logs.
- DSQA harness logs include full contexts unexpectedly.

**Phase to address:**
Phase 05-end-to-end-observability-and-run-history

---

### Pitfall 12: "Looks done" tests check the wrong layer

**What goes wrong:**
Unit tests validate extraction returns "some text", but do not validate deterministic set output semantics under DSQA comparator rules.

**Why it happens:**
- Tests stop at "type correctness" (string/array existence).
- No golden end-to-end tests for set equivalence.

**How to avoid:**
- Add golden end-to-end tests: `(url, objective) -> excerpts/full_content -> agent set output -> DSQA comparator`.
- Include tests that intentionally vary whitespace/casing to ensure canonicalization is correct.

**Warning signs:**
- Extractor tests pass, DSQA metrics still fail.
- Changes to normalization cause accuracy regressions without unit test failures.

**Phase to address:**
Phase 05-end-to-end-observability-and-run-history

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|-----------------|-----------------|
| LLM-based excerpt selection without deterministic constraints | Faster iteration | Flaky eval, hard debugging | Never for set-equivalence eval; allow only with strict determinism + validators |
| Relying on natural language output format for DSQA | Quick wiring | Parsing/contract brittleness | Never for `output_format="set"` |
| Caching only by URL | Simpler | Wrong excerpts for different objectives | Only for HTTP-full_content mode where objective is irrelevant |
| Using fixed sleeps for JS readiness | Easy to implement | Timing flakiness across machines | Only as a temporary fallback with hard caps and readiness checks |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|------------------|------------------|
| Playwright rendering | Treating "network idle" as a reliable readiness signal | Use deterministic readiness checks (selectors/content presence) plus time caps; record `render_used` |
| PDF extraction | Assuming extracted text equals human-readable content | Detect near-empty text and return structured fallback; do not proceed as if content was extracted |
| Excerpt contract -> agent prompt | Prompt expects fields not present in tool output | Schema-validate and test end-to-end mapping |
| DSQA harness -> agent output | Evaluator compares different normalization than the agent output expects | Share canonicalization and set-comparison logic between generator and evaluator |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|-----------------|
| "Cheap" excerpt budget not enforced | Cost spikes, slower eval, larger payloads | Hard caps at extraction/serialization boundary; meta budget accounting | When throughput increases (more pages per run) |
| Unbounded retries/timeouts | Runs hang or cost runaway | Cap retries/timeouts per stage; fail closed with status | When site behavior changes (captcha, slow JS) |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| SSRF via arbitrary URLs | Internal network access | Block private IP ranges; scheme restrictions; redirect validation |
| Logging raw provider internals | Data leakage | Do not log raw provider payloads; redact + cap |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Non-actionable fallback states | Users see "no answer" without understanding why | Always return structured fallback reasons in `meta.status` |

## "Looks Done But Isn't" Checklist

- [ ] **JS rendering status is visible:** `meta.render_used` and `meta.status` must be present for both success and fallback.
- [ ] **Excerpt determinism is enforced:** repeated runs on same `(url, objective)` yield the same canonical set items (under fixed pipeline version).
- [ ] **Budget is hard-capped:** `excerpts[]` count and per-excerpt length are enforced and reflected in `meta`.
- [ ] **Set output is parseable and prose-free:** `output_format="set"` returns a strict format that the DSQA comparator can parse reliably.
- [ ] **Evaluation harness matches production constraints:** DSQA runs use the same excerpt mode and excerpt budgeting logic as the runtime.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|-----------------|
| Excerpts become non-deterministic | HIGH | Freeze pipeline version, add determinism + canonical sort keys, update comparator normalization, rerun golden DSQA samples |
| JS render returns incomplete DOM | MEDIUM | Tighten readiness checks, record render signals, add render_used-based regression tests |
| PDF extraction returns empty text | LOW/MEDIUM | Add/raise thresholds, add fallback reasons, gate excerpt selection to extracted-text quality |
| Harness semantics mismatch | HIGH | Write harness unit tests for set normalization, align canonicalization, then rerun DSQA metrics |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Non-deterministic excerpt selection breaks DSQA | Phase 02; Phase 03 | Golden DSQA samples: same inputs => stable `excerpts[]` and stable set output parse + identical Fully Correct results |
| Output contract drift (prose leaks into set mode) | Phase 03; Phase 04 | Contract tests for parser+validator: reject prose/non-JSON; DSQA harness parse success rate stays near 100% |
| Fully Correct evaluation harness compares the wrong thing | Phase 05 | Harness self-tests with synthetic cases where ordering/whitespace differs but set-equivalence should be stable |
| JS rendering silently incomplete DOM | Phase 02 | Regression tests on JS-heavy fixtures: `render_used=true` correlates with higher extraction quality and consistent excerpt sets |
| PDF extraction returns empty/garbled | Phase 02 | PDF fixture matrix: text PDFs vs scanned/encrypted; ensure fallback reasons and excerpt gating behave deterministically |
| Budget enforcement partial | Phase 02; Phase 05 | Meta budget accounting matches configured limits and DSQA runtime/cost stays bounded |
| Cache key mistakes | Phase 02 | A/B objective tests: same url + different objective produces different excerpt sets; cache key includes objective |
| Boilerplate contamination | Phase 02 | Golden excerpt snapshots across HTML/JS/PDF conversion modes |
| Tool/runtime schema mismatch | Phase 03; Phase 05 | Schema validation tests and integration tests across tool output -> prompt mapping -> set output parse |
| SSRF unsafe URL handling | Phase 01; Phase 02 | Unit tests for URL validation: blocked schemes/IP ranges/redirect escape paths |
| Telemetry leaks sensitive payloads | Phase 05 | Log sampling tests: assert no raw bodies and payload caps |
| Tests check wrong layer | Phase 05 | End-to-end golden tests covering DSQA comparator, not just extraction unit tests |

## Sources

- [OWASP Server-Side Request Forgery (SSRF)](https://owasp.org/www-community/attacks/Server_Side_Request_Forgery)
- [Microsoft Playwright: Waiting for elements / load states](https://playwright.dev/docs/loading)
- [PyMuPDF documentation](https://pymupdf.readthedocs.io/)

---
*Pitfalls research for: web extraction agents (objective-driven excerpts + deterministic set outputs, incl. JS/PDF + DSQA eval)*
*Researched: 2026-03-20*

