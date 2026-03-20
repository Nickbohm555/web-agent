# Stack Research

**Domain:** Web extraction agent (FastAPI/LangChain + JS/PDF handling + objective excerpts)
**Researched:** 2026-03-20
**Confidence:** MEDIUM

## Recommended Stack

### Core Technologies
| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| FastAPI | 0.115.12 | API/tool surface (`/api/agent/run`) | Already in repo; stable and ergonomic for tool orchestration |
| HTTPX | 0.28.1 | Bounded HTTP fetch + retries | Already in repo; deterministic request/timeout control |
| LangChain | 0.3.27 | Agent/tools abstractions | Already in repo; integrates naturally with existing runtime |
| LangGraph | 0.6.11 | Agent runtime graphing | Already in repo; useful as the runtime grows |
| Playwright (Python) | 1.58.0 | Safe headless rendering for JS-heavy pages | De-facto standard headless browser automation for web extraction; supports request interception and deterministic browser contexts |
| PyMuPDF (pymupdf) | 1.27.2.2 | Reliable PDF text extraction (vector text) | Fast, accurate text extraction for most "real" PDFs; works well as a first attempt |
| OCRmyPDF | 17.3.0 | OCR fallback for scanned PDFs | Adds an OCR text layer to scanned PDFs, enabling downstream text excerpting |
| trafilatura | 2.0.0 | Main-content extraction from HTML | Already in repo; good HTML-to-text/markdown conversion for evidence extraction |
| rank-bm25 | 0.2.2 | Cheap deterministic objective-driven excerpt ranking | Lexical BM25 scoring is deterministic, CPU-cheap, and budget-friendly |
| sentence-transformers | 5.3.0 | Optional local semantic scoring/reranking | Enables higher-recall semantic matching when BM25 misses synonyms; can be deterministic when run on CPU with fixed models |

### Supporting Libraries
| Library | Version | Purpose | When to Use |
|---------|---------|---------|--------------|
| pydantic-settings | 2.8.1 | Configuration via env vars | Always for runtime settings like timeouts/budgets |
| tenacity | 9.0.0 | Retry policy wrappers | Useful for browser/PDF fallbacks (bounded attempts) |
| numpy | (install via deps) | BM25 math | Required by `rank-bm25` |
| scikit-learn | (pin >=1.4) | TF-IDF baseline (optional) | If you want a second deterministic scoring channel alongside BM25 |

### Development Tools
| Tool | Purpose | Notes |
|------|---------|-------|
| Docker (Compose) | Run extractor + headless Chromium in isolated environment | Keep browser execution isolated from API network and filesystem as much as possible |
| Playwright system deps | Ensure Chromium can run in containers | Install via Playwright "with-deps" or equivalent OS packages |

## Stack Patterns by Variant

### If you need "cheap deterministic" excerpts (v1 default)
- Use `rank-bm25` over candidate sentences/paragraphs extracted via `trafilatura` output (or DOM text).
- Because BM25 is lexical, deterministic, and avoids embedding/LLM variability.

### If BM25 underperforms (only when budget permits)
- Add an optional reranking pass using `sentence-transformers` embeddings or a CrossEncoder reranker.
- Because semantic models increase recall for synonym-heavy objectives, at the cost of more CPU/time.

### If the PDF has low/no extracted text (scanned PDFs)
- First try `PyMuPDF` text extraction.
- If extracted text length/quality is below a threshold, run `OCRmyPDF`, then re-extract with `PyMuPDF`.
- Because OCRmyPDF produces a searchable text layer that’s easy to excerpt deterministically.

## Tradeoffs (What you gain / what you pay)

### 1) Rendering JS-heavy pages safely
| Choice | Tradeoff | Recommendation |
|--------|-----------|----------------|
| Playwright | Higher overhead than raw HTTP; needs browser sandboxing and careful network control | Use Playwright with per-request isolated browser contexts, request interception, strict timeouts, and CPU/memory caps at the container level |
| DOM text extraction (`page.evaluate`/`innerText`) vs full HTML | DOM text is safer/smaller but may miss some structure; full HTML can be harder to normalize | Prefer DOM text or rendered "readable" HTML passed into `trafilatura` for evidence extraction |

Safety guidance (stack-level):
- Do not treat rendered output as trustworthy HTML; do not return raw DOM/HTML to clients.
- Use `context.route(...)` to block downloads, limit third-party requests, and prevent high-risk schemes where possible.
- Enforce strict navigation + selector wait timeouts and max page size to keep extraction budgets bounded.
- Prefer sandboxed Chromium in containers when feasible; if you must disable sandbox (common in some Docker setups), rely on container isolation + seccomp/AppArmor controls as compensation.

### 2) Extracting text from PDFs reliably
| Choice | Tradeoff | Recommendation |
|--------|-----------|----------------|
| PyMuPDF first | Fast; works great for vector/text PDFs but returns little for scanned/image-only PDFs | Use as the first pass |
| OCRmyPDF fallback | Expensive CPU-wise; requires system OCR tooling (Tesseract) | Trigger only when "low extracted text" thresholds trip |

### 3) Deterministic, cheap excerpt selection/ranking
| Choice | Tradeoff | Recommendation |
|--------|-----------|----------------|
| rank-bm25 | Lexical match; weaker with synonyms/semantic paraphrases | Default v1 ranking channel (budget-safe) |
| TF-IDF + heuristics | Similar budget to BM25; may behave differently with short queries | Good deterministic baseline/secondary signal |
| sentence-transformers reranking | Better semantic recall but adds CPU/time variability and model complexity | Use only as optional fallback for difficult objectives |

Determinism techniques (must-haves for set-output mode):
- Fixed preprocessing (lowercasing, Unicode normalization, stable regex tokenization).
- Stable tie-breaking (score desc, then candidate index).
- No LLM in the v1 excerpt selection loop.

## Alternatives Considered

### JS rendering
| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| Playwright | Puppeteer (Node) | If the extraction stack were Node-first; otherwise Python integration is weaker |
| Playwright | Pyppeteer/Selenium | If you only need very basic rendering and can accept less reliable modern JS support |

### PDF text extraction
| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| PyMuPDF | pdfminer.six | If you need very specific PDF parsing control; usually slower and more fragile across PDF variants |
| OCRmyPDF | pytesseract + pdf2image | If you need custom OCR pipelines; OCRmyPDF is simpler and produces a searchable PDF layer |

### Excerpt ranking
| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| rank-bm25 | scikit-learn TF-IDF | If you want simpler scoring or easier debugging |
| rank-bm25 | embeddings + cosine similarity | If objective semantics are critical and you can afford compute |

## What NOT to Use

| Avoid | Why | Use Instead |
|------|-----|--------------|
| LLM-based excerpt selection/ranking in the extractor | Non-determinism, higher cost, harder to debug for eval | Deterministic BM25/TF-IDF ranking in v1; optionally rerank with local models later |
| Unbounded rendering/wait loops | Can explode budgets and cause timeouts | Strict Playwright timeouts + bounded "max pages/requests" policies |

## Version Compatibility

| Package | Compatible With | Notes |
|-----------|-----------------|-------|
| Playwright 1.58.0 | Python >=3.9 | Repo uses Python 3.12 in `backend/Dockerfile` |
| PyMuPDF 1.27.2.2 | Python >=3.10 | Repo OK |
| OCRmyPDF 17.3.0 | Python >=3.11 | Repo OK |

## Sources

- https://pypi.org/project/playwright/ (Playwright 1.58.0; version history includes 2025 releases)
- https://pypi.org/project/PyMuPDF/ (PyMuPDF 1.27.2.2; version history includes 2025 releases)
- https://pypi.org/project/ocrmypdf/ (OCRmyPDF 17.3.0)
- https://pypi.org/project/rank-bm25/ (rank-bm25 0.2.2)
- https://pypi.org/project/sentence-transformers/ (sentence-transformers 5.3.0)

---
*Stack research for: Web extraction agent (JS + PDF + deterministic objective excerpts)*
*Researched: 2026-03-20*

