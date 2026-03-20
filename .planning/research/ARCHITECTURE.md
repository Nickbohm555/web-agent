# Architecture Research

**Domain:** Tool-based web retrieval + extraction for LLM evidence
**Researched:** 2026-03-20
**Confidence:** MEDIUM

## Standard Architecture

### System Overview

The system is best modeled as an LLM agent that can call *canonical tools* (`web_search`, `web_crawl`). All “messy web” handling (JS rendering, PDF extraction, excerpt selection) must live *behind the tool contract* so the agent always sees a stable, normalized output shape.

```text
                ┌────────────────────────────────────────┐
Client ──HTTP──▶│ FastAPI: /api/agent/run                │
                └────────────────────────────────────────┘
                                     │
                                     ▼
                           ┌───────────────────┐
                           │ Agent Runtime     │
                           │ (LangChain/LangGraph)│
                           └───────────────────┘
                             │           │
                      tool: web_search  tool: web_crawl
                             │           │
                             ▼           ▼
                ┌─────────────────┐  ┌─────────────────────────────┐
                │ Search Tool     │  │ Crawl Tool (web_crawl)       │
                └─────────────────┘  └─────────────────────────────┘
                                             │
                                             ▼
                          ┌──────────────────────────────────────┐
                          │ Crawl Pipeline (single URL)          │
                          │ 1) Fetch (bounded)                  │
                          │ 2) Content-type routing           │
                          │ 3) Render/Extract (HTML/JS/PDF) │
                          │ 4) Quality checks                 │
                          │ 5) Excerpt selection (optional) │
                          │ 6) Normalize to response contract │
                          └──────────────────────────────────────┘
                                             │
                                             ▼
                                  ┌────────────────────────┐
                                  │ Tool Output Contract   │
                                  │ (success or error)     │
                                  └────────────────────────┘
                                             │
                                             ▼
                           ┌──────────────────────────────────┐
                           │ Agent Synthesis                  │
                           │ (final_answer string only)     │
                           └──────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|------------------|--------------------------|
| `Agent Runtime` | Build agent with canonical tool bindings, set bounded recursion, extract `final_answer` string | `backend/agent/runtime.py` |
| `Tool Adapter` (`web_crawl`) | Validate input, orchestrate the crawl pipeline, return success or structured error envelope | `backend/app/tools/web_crawl.py` |
| `HttpFetchWorker` | Bounded network retrieval (timeout, max bytes), redirects, content-type validation, retry boundaries | `backend/app/crawler/http_worker.py` |
| `ContentTypeRouter` | Decide extraction path (HTML vs JS-render vs PDF) using content-type + quality heuristics | new module (e.g. `backend/app/crawler/router.py`) |
| `HTML Extractor` | Convert HTML bytes/text into markdown/text (current: `trafilatura`) | `backend/app/crawler/extractor.py` |
| `JS Renderer` | Render JS-heavy pages (deterministically) and return rendered HTML/text for downstream extraction | new module (e.g. `backend/app/crawler/renderers/playwright_renderer.py`) |
| `PDF Extractor` | Convert PDF bytes into text and/or structured text blocks for excerpt selection | new module (e.g. `backend/app/crawler/renderers/pymupdf_extractor.py`) |
| `Quality Gates` | Detect “too little content”, unsupported types, render failures; emit `fallback_reason` | part of crawl pipeline |
| `Excerpt Selector` | Given extracted full content and an `objective/search_queries` signal, pick N deterministic excerpt snippets under a strict char budget | new module (e.g. `backend/app/excerpts/selector.py`) |
| `Normalizer` | Produce a stable per-URL response contract: `url`, `title`, `publish_date`, `excerpts[]`, `full_content`, `meta` and fallback states | updated contract models |
| `Evaluation Harness` | Run DSQA-like tasks end-to-end, parse `final_answer`, compute Fully Correct accuracy, output reports | new `backend/eval/` package |

## Recommended Project Structure

This is the target conceptual structure; it should map to your existing `backend/app/crawler/*` and `backend/app/tools/*` layout.

```text
backend/
  app/
    tools/
      web_crawl.py               # tool adapter; wraps pipeline
      web_search.py
    contracts/
      tool_errors.py
      web_crawl.py              # success/error schemas (extended for v1)
      web_search.py
    crawler/
      http_worker.py           # bounded fetch + retries
      router.py                # content routing decisions
      extractor.py            # HTML extraction (trafilatura)
      renderers/
        js_renderer.py         # Playwright-based rendering
        pdf_extractor.py       # PyMuPDF-based extraction
      quality.py               # quality gates + fallback reasons
    excerpts/
      selector.py              # objective/query-driven excerpt selection
      budget.py                # char budget enforcement, truncation rules
    normalize/
      response_contract.py     # build ExtractResponse / WebCrawlSuccess models
  eval/
    dsqa/
      dataset_loader.py       # load prompts, caching, validation
      runner.py               # invoke agent end-to-end
      output_parser.py       # parse/validate `final_answer` set mode
      scorer.py              # Fully Correct exact-set equivalence
      report.py              # aggregated accuracy + per-sample diagnostics
```

### Structure Rationale

- `crawler/` owns *how to turn bytes into text/markdown*, including multiple rendering/extraction paths; `tools/` owns *how to expose that functionality to the agent*.
- `excerpts/` owns *how to turn full extracted text into excerpt snippets*; it should not know about network fetching or LLM agent internals.
- `normalize/` (or “contract builders”) centralizes output shaping so `web_crawl` returns a stable schema no matter which extractor succeeded.
- `eval/` is intentionally offline and separate from tool runtime so correctness can be measured without coupling to production prompt changes.

## Architectural Patterns

### Pattern 1: Bounded Fetch → Router → Extractor

**What:** Always separate (a) bounded retrieval, (b) content-type routing, and (c) extraction into dedicated modules, with clear data objects between steps.

**When:** When you need consistent fallback reasons (`unsupported-content-type`, `low-content-quality`, `network-error`) and want JS/PDF to be “add-on” paths behind a stable contract.

**Trade-offs:** Slight upfront complexity; prevents future extraction behavior from becoming a tangled “if/else” inside the tool.

**Example:**

```python
# conceptual data flow
fetch_result = http_fetch_worker.fetch(url)
extraction_plan = router.plan(content_type, fetch_result, quality_hints)
raw_extraction = extractor_registry.run(extraction_plan, fetch_result.body)
quality = quality_gates.evaluate(raw_extraction)
normalized = normalizer.to_contract(raw_extraction, quality, fetch_result.meta)
```

### Pattern 2: “Optional Work” Based on Mode Flags

**What:** The crawl pipeline supports toggles like `full_content_mode` and `excerpt_mode` without forcing expensive operations. Example:
- In `excerpt_mode`, you may skip full markdown serialization or reduce output length early.
- In `full_content_mode`, you return complete normalized markdown (with links preserved).

**When:** When cost/budget matters (JS rendering and PDF parsing can be expensive) and you need deterministic outputs across modes.

**Trade-offs:** Requires careful contract design so `meta` includes what was actually performed (e.g. `render_used`).

### Pattern 3: Deterministic Excerpt Selection as a Pure Function

**What:** Implement excerpt selection (and excerpt ordering) as deterministic logic (stable sorting, explicit truncation rules, no uncontrolled randomness).

**When:** When downstream eval requires exact matching and your agent’s tool outputs must be consistent.

**Trade-offs:** Some “semantic” ranking quality may lag LLM-based selection; mitigate by combining objective/query signals with robust heuristics (sentence scoring, overlap, density).

## Data Flow

### Request Flow (end-to-end)

```text
[Client prompt]
    ↓
[FastAPI /api/agent/run]
    ↓ (calls)
[Agent runtime: run_agent_once(prompt)]
    ↓
[LLM agent]
    ↓ tool calls
[web_search] / [web_crawl]
    ↓ tool outputs
[LLM synthesis]
    ↓
[Agent returns only `final_answer` string]
```

### Key Data Flows

1. **Crawl pipeline: fetch → extract → select → normalize**

```text
Input: { url, optional objective, optional search_queries, mode flags }
    ↓
Validate input schema (tool adapter)
    ↓
HttpFetchWorker.fetch(url)
    ↓
ContentTypeRouter.plan():
   - HTML -> HTML extractor (trafilatura)
   - HTML but low-quality -> optional JS render path
   - PDF -> PDF extractor
    ↓
Raw extraction results:
   - extracted full text/markdown OR empty with fallback reason
    ↓
Quality Gates:
   - enforce MIN extracted size
   - map failures to fallback_reason and state
    ↓
Excerpt Selector (only if excerpt_mode requested):
   - take extracted content
   - rank/select top K excerpts using objective/query overlap
   - enforce char budget per excerpt and max excerpt count
    ↓
Normalizer:
   - build `WebCrawlSuccess` contract:
     url, final_url, title, publish_date, excerpts[], full_content, status_code,
     content_type, fallback_reason, meta
    ↓
Return tool JSON payload (success or ToolErrorEnvelope)
```

2. **Deterministic “set output mode” despite `final_answer` being a string**

Because the API only returns `final_answer: str`, deterministic set output must be achieved at the *prompt + parsing/normalization* layers:

```text
Evaluation harness constructs a prompt:
 - instructs model to output ONLY a canonical JSON array (set mode)
 - instructs the model to sort items and deduplicate
 - forbids any prose or markdown
    ↓
Agent runtime extracts `final_answer` string as-is
    ↓
Optional: FinalAnswerNormalizer (recommended) tries to:
 - parse JSON array of strings
 - trim/normalize whitespace
 - deduplicate
 - sort deterministically
 - re-serialize as a canonical string
    ↓
Scorer parses canonical set from `final_answer` and performs exact-set equivalence
```

### State Management

No shared mutable state is required at the tool layer. Persist only per-run metadata in `meta` for:
- fetch attempts/duration
- render_used (boolean)
- extraction state/fallback reasons
- (if applicable) excerpt selection budget usage

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|---------------------------|
| 0-1k users | Single-process tool runtime; bounded concurrency; reuse HTTP client pools |
| 1k-100k users | Add worker-level concurrency limits for Playwright/PDF parsing; introduce caching (per URL) where safe; enforce per-request time budgets per module |
| 100k+ users | Split render/extract into job workers (queue) and keep API responsive; require stronger caching and stronger timeouts per module |

### Scaling Priorities

1. **First bottleneck:** JS rendering and PDF parsing time/CPU; mitigate by routing only when needed (quality gates) and bounding render time.
2. **Second bottleneck:** Memory spikes from large PDFs/bodies; mitigate via strict max bytes and streaming where possible (module-level).

## Anti-Patterns

### Anti-Pattern 1: Monolithic `web_crawl` with tangled branching

**What people do:** Put fetch, routing, HTML extraction, JS rendering, PDF parsing, excerpt selection, and contract shaping all inside one function.

**Why it’s wrong:** Hard to test, hard to add modes (full vs excerpts), and failures become ambiguous (bad fallback reasons).

**Do this instead:** Implement the pipeline as discrete modules with a single “normalized intermediate representation” passed step to step.

### Anti-Pattern 2: Nondeterministic excerpt ordering

**What people do:** Use unordered sets/dicts or LLM generation to pick excerpts without canonical ordering.

**Why it’s wrong:** DSQA-style “Fully Correct” scoring typically requires exact set equivalence.

**Do this instead:** Deterministically rank excerpts and deterministically serialize the selected excerpt list.

### Anti-Pattern 3: Returning raw tool internals in user-visible output

**What people do:** Leak fetch internals/provider payloads or include raw HTML/PDF bytes.

**Why it’s wrong:** Breaks safety and makes outputs noisy and unstable for eval.

**Do this instead:** Always return structured `meta` summary + normalized content excerpts/full_content only, and avoid raw bodies.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|------------------------|-------|
| Serper (`web_search`) | Provider client + retries + normalization | keep provider internals internal |
| OpenAI provider (agent synthesis) | LLM agent with bounded recursion + `temperature=0` | final output must be deterministic in set mode |
| Playwright (JS rendering) | Render module with strict timeouts and bounded output | keep HTML/text size bounded |
| PyMuPDF (PDF parsing) | PDF extractor module with bounded parsing and text normalization | extract only text needed for excerpts/full_content |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|------|
| `HttpFetchWorker` → `ContentTypeRouter` | Typed fetch result object (`body`, `content_type`, `final_url`, `meta`) | keep network layer ignorant of extraction strategy |
| `ContentTypeRouter` → extractors | “Plan” object selecting extractor + mode flags | routing is the only place that decides *which* path runs |
| Extractors → Quality Gates | Raw extraction (text/markdown + structured hints) | quality gates set `state` + `fallback_reason` |
| Quality Gates → Excerpt Selector | Full extracted text/markdown + objective inputs | excerpt selector should be pure/deterministic |
| Excerpt Selector → Normalizer | Excerpt candidates + budget context | normalizer enforces contract schema |
| Tool Adapter → Agent Runtime | JSON payloads or error envelopes | tool output must be stable for prompting |
| Evaluation Harness → Agent Runtime | prompt strings + parses `final_answer` | harness owns scoring semantics |

## Recommended Build Order

1. **Extend response contracts before implementing new behaviors**
   - Update `backend/app/contracts/web_crawl.py` to add: `excerpts[]`, `full_content`, `title`, `publish_date`, and richer `meta` (`render_used`, extraction state).
   - Keep error envelope behavior unchanged: tool adapters should still return structured error envelopes on failure.

2. **Introduce the pipeline skeleton (interfaces + routing)**
   - Add `ContentTypeRouter` and a registry/dispatch layer for extractors (HTML now, then JS/PDF later).
   - Refactor `web_crawl` to call: fetch → route → extract → quality → (optional) excerpts → normalize.

3. **Implement JS/PDF modules behind the router**
   - Update fetch/content-type support rules so the pipeline can receive PDF bytes.
   - Add JS renderer module and wire it behind a “quality gate” (e.g., only attempt JS render if initial HTML extraction is low-quality).
   - Add PDF extractor module and wire it for PDF extraction states.

4. **Implement deterministic excerpt selection**
   - Build `ExcerptSelector` as a deterministic function with:
     - `objective` as primary signal
     - `search_queries` as secondary ranking signal
     - strict budget: `max_excerpts`, `max_chars_per_excerpt`, and deterministic excerpt ordering
   - Ensure excerpt output contains stable formatting (e.g., trimmed strings, no nondeterministic punctuation normalization).

5. **Wire “set output mode” for DSQA-style eval**
   - Update system prompt and/or evaluation prompt templates to force `final_answer` to be a canonical JSON array string with no prose.
   - (Recommended) Add a `FinalAnswerNormalizer` step in `backend/agent/runtime.py` that parses JSON arrays, sorts/deduplicates, and re-serializes canonically when possible.

6. **Add evaluation harness (end-to-end)**
   - Implement DSQA runner that:
     - loads dataset samples
     - constructs prompts in set-output mode
     - calls the agent end-to-end
     - parses canonical sets from `final_answer`
     - computes Fully Correct exact-set equivalence and aggregates metrics
   - Add “golden prompt” tests ensuring parsing and canonicalization are stable even when the model output has minor whitespace differences.

## Sources

- Existing repo architecture contracts and tool pipeline docs:
  - `backend/app/tools/web_crawl.py`
  - `backend/app/contracts/web_crawl.py`
  - `backend/app/crawler/http_worker.py`
  - `backend/app/crawler/extractor.py`
  - `backend/agent/runtime.py`
  - `BACKEND_TOOL_DATA_FLOW.md`
  - `TOOLS_DATA_FLOW.md`
- Domain requirements captured in:
  - `.planning/PROJECT.md`
  - `features.md`

