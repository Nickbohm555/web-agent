# Phase 02: Search and Crawl Tool Capability - Research

**Researched:** 2026-03-17  
**Domain:** Python tool implementations for Serper-backed search and in-house crawl extraction in a LangGraph/LangChain agent runtime  
**Confidence:** HIGH

## Summary

Phase 02 should implement exactly two Python tools, `web_search` and `web_crawl`, with strict Pydantic contracts, deterministic normalization, and typed error reporting. The fastest path is to keep tool code independent from graph orchestration details (Phase 03), but shaped for LangChain/LangGraph tool-calling (`@tool`, snake_case names, structured args, structured return objects). This keeps the phase scoped to AGENT-02 and AGENT-03 while making the next phase trivial.

For `web_search`, use `httpx` + Serper POST integration and normalize into a stable list of `{title, url, snippet, rank}` entries. For `web_crawl`, use HTTP-first retrieval via `httpx` and main-content extraction via Trafilatura (`output_format="markdown"` plus plain-text output), with a low-content-quality fallback state instead of silent empties. Reuse the existing TypeScript repository patterns: explicit retryable vs non-retryable errors, mapped error kinds, and metadata blocks for debugging.

Both tools should always return either: (a) a contract-valid success payload, or (b) a contract-valid error payload with machine-readable fields (`kind`, `retryable`, `status_code`, `attempts`, `timings`, `operation`). This directly satisfies success criterion #3 (explicit, debuggable failures) and prevents hidden failure modes in later agent orchestration.

**Primary recommendation:** Build Phase 02 around a `contracts -> clients/workers -> tool adapters` architecture with strict Pydantic validation and typed error envelopes as first-class outputs.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `langchain` / `langchain-core` | Current stable (v1-era docs) | Tool definitions via `@tool`, tool schema generation, runtime compatibility | Official docs define canonical tool interface used by LangGraph tool execution |
| `pydantic` | `2.12.5` (docs) | Request/response/error schema validation | Canonical Python validation layer; strict contracts and clear validation errors |
| `httpx` | Current stable | Outbound HTTP for Serper + crawl URL fetch | Mature sync/async API, timeouts, status handling, exception hierarchy |
| `tenacity` | Current stable | Bounded retries/backoff for transient failures | Explicit retry policy primitives (attempt count, backoff, jitter, retry predicates) |
| `trafilatura` | `2.0.0` (docs) | Main-content extraction to text/markdown | Extraction-focused and supports markdown output directly |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `urllib.robotparser` (stdlib) | Python `3.14.x` docs | Parse `robots.txt` allow/deny and crawl-delay | If Phase 02 includes basic crawl politeness gate (recommended minimal check) |
| `pytest` | Current stable (`pytest-9.x` docs examples) | Unit/integration tests | Default Python testing stack for contract + retry + error-path coverage |
| `fastapi` | Current stable | API exposure of tool execution for frontend/backend integration | If this phase needs callable HTTP endpoints before full agent loop phase |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `trafilatura` | `readability-lxml` + custom cleanup | More custom code/heuristics needed for markdown/text consistency |
| `tenacity` | Custom retry loop | Reinvents backoff/stop/retry classification logic; easy to get wrong |
| Direct dict contracts | `pydantic` models | Dict-only is faster to start but weakens schema guarantees and error clarity |

**Installation:**
```bash
pip install langchain langchain-core pydantic httpx tenacity trafilatura pytest
```

## Architecture Patterns

### Recommended Project Structure
```text
python_backend/
├── tools/                 # LangChain tool adapters (web_search, web_crawl)
├── contracts/             # Pydantic models: requests, responses, errors
├── providers/
│   └── serper_client.py   # Serper transport + mapping
├── crawler/
│   ├── http_worker.py     # URL fetch, timeout, redirects
│   └── extractor.py       # Trafilatura extraction + quality checks
├── core/
│   ├── errors.py          # Typed error kinds + mapping
│   └── retry.py           # Tenacity policy wrappers
└── tests/                 # Unit + integration contract tests
```

### Pattern 1: Tool-Adapter Boundary
**What:** Keep tool functions thin; validate input, call internal service, return validated output.  
**When to use:** Always, for both `web_search` and `web_crawl`.  
**Example:**
```python
# Source: https://docs.langchain.com/oss/python/langchain/tools.md
from langchain.tools import tool
from pydantic import BaseModel, Field

class WebSearchInput(BaseModel):
    query: str = Field(min_length=1, description="Search query")
    max_results: int = Field(default=5, ge=1, le=10)

@tool("web_search", args_schema=WebSearchInput)
def web_search(query: str, max_results: int = 5) -> dict:
    # Delegate to provider client; always return contract-valid object
    return search_service(query=query, max_results=max_results)
```

### Pattern 2: HTTP Client + Explicit Retry Classification
**What:** Retry only transient failures (`429`, `5xx`, network timeout/reset), fail fast on invalid requests (`4xx` non-429).  
**When to use:** Serper calls and crawl fetch calls.  
**Example:**
```python
# Source: https://www.python-httpx.org/quickstart/ and https://tenacity.readthedocs.io/en/latest/
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

class TransientHttpError(Exception):
    pass

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.25, min=0.25, max=2.0),
    retry=retry_if_exception_type((httpx.RequestError, TransientHttpError)),
    reraise=True,
)
def call_serper(payload: dict, api_key: str) -> dict:
    r = httpx.post(
        "https://google.serper.dev/search",
        headers={"x-api-key": api_key, "content-type": "application/json"},
        json=payload,
        timeout=5.0,
    )
    if r.status_code == 429 or r.status_code >= 500:
        raise TransientHttpError(f"retryable status {r.status_code}")
    r.raise_for_status()
    return r.json()
```

### Pattern 3: Extraction Result-State Envelope (Never Silent Empty)
**What:** Represent crawl extraction outcome as stateful result (`ok`, `low_content_quality`, `unsupported_content_type`, `network_error`).  
**When to use:** `web_crawl` internal extraction and final response shaping.  
**Example:**
```python
# Source: https://trafilatura.readthedocs.io/en/latest/corefunctions.html#extract
import trafilatura

def extract_markdown(html: str) -> dict:
    md = trafilatura.extract(html, output_format="markdown", fast=True)
    text = trafilatura.extract(html, output_format="txt", fast=True)
    if md is None and text is None:
        return {"state": "low_content_quality", "text": "", "markdown": ""}
    return {
        "state": "ok" if (text or "").strip() else "low_content_quality",
        "text": (text or "").strip(),
        "markdown": (md or "").strip(),
    }
```

### Anti-Patterns to Avoid
- **Tool logic directly in graph nodes:** Harder to test and reuse; keep tools/services standalone.
- **Free-form error strings only:** Breaks debuggability; always include structured error fields.
- **Returning raw provider payloads:** Couples agent to provider schema; normalize first.
- **Retrying all 4xx:** Wastes credits/time; retry only transient categories.
- **Treating empty extraction as success:** Leads to silent failures and poor agent behavior.

## Data Contracts (Planning-Critical)

Keep exactly two tool contracts with stable field names:

- `web_search` response:
  - `query: str`
  - `results: list[{title:str, url:str, snippet:str, rank:{position:int, provider_position:int|None}}]`
  - `metadata: {result_count:int, provider:str}`
  - `meta: {operation, attempts, retries, duration_ms, timings}`

- `web_crawl` response:
  - `url: str`
  - `final_url: str`
  - `text: str`
  - `markdown: str`
  - `status_code: int|None`
  - `content_type: str|None`
  - `fallback_reason: str|None` (`network-error`, `low-content-quality`, `unsupported-content-type`)
  - `meta: {operation, attempts, retries, duration_ms, timings}`

- Error envelope (shared):
  - `error: {kind, message, retryable, status_code?, attempt_number?, operation}`
  - `meta: {...timings...}`

## Implementation Slices (Recommended)

1. **Slice 02-01A (Search Contract + Serper Client)**  
   Build Pydantic schemas + transport + normalization mapper.
2. **Slice 02-01B (Search Tool Adapter + Error Envelope)**  
   Expose `@tool("web_search")`, enforce response/error contract.
3. **Slice 02-02A (Crawl HTTP Worker + Retry/Error Mapping)**  
   Fetch URL, handle redirects/timeouts/status classification.
4. **Slice 02-02B (Extraction + Response Contract)**  
   Trafilatura extraction, quality threshold, fallback reason mapping.
5. **Slice 02-02C (Crawl Tool Adapter + Contract Tests)**  
   Expose `@tool("web_crawl")`, complete end-to-end test matrix.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Input/output schema validation | Ad-hoc dict checks | `pydantic` models | Better error detail, strict typing, reusable contracts |
| Retry/backoff policy | Manual loops/sleeps | `tenacity` | Reliable stop/wait/retry composition with clear semantics |
| Main-content extraction | Regex/manual DOM heuristics | `trafilatura` | Handles noisy pages, supports markdown/text outputs |
| robots.txt parsing | Custom parser | `urllib.robotparser` | Built-in parser with `can_fetch`, `crawl_delay`, `request_rate` |
| Tool schema wiring | Custom JSON schema plumbing | LangChain `@tool` + `args_schema` | Native integration with tool-calling chat models |

**Key insight:** Phase 02 risk is not feature count but contract drift and edge-case failures; established libs eliminate most edge-case burden.

## Common Pitfalls

### Pitfall 1: Provider payload leakage
**What goes wrong:** Raw Serper fields (including unused/unstable fields) leak into tool output.  
**Why it happens:** Skipping explicit mapping layer.  
**How to avoid:** Map only canonical fields and validate final response model.  
**Warning signs:** Tests assert on provider-specific fields; response shape changes after provider update.

### Pitfall 2: "Success" with unusable crawl content
**What goes wrong:** Tool returns 200 + empty text without signaling failure mode.  
**Why it happens:** No quality threshold/result-state design.  
**How to avoid:** Enforce extraction state + `fallback_reason` when content quality is low.  
**Warning signs:** Empty `text` and `markdown` in nominal success branch.

### Pitfall 3: Over-retrying non-retryable errors
**What goes wrong:** 400/401/403 requests retried repeatedly.  
**Why it happens:** Single catch-all retry policy.  
**How to avoid:** Separate transient and terminal classes; bounded retry attempts.  
**Warning signs:** High attempts with identical 4xx status.

### Pitfall 4: Tool naming/schema mismatch
**What goes wrong:** Agent fails to call tools reliably across providers.  
**Why it happens:** Non-snake-case names, ambiguous docstrings, unstable args.  
**How to avoid:** Keep names `web_search` and `web_crawl`; clear docstrings and args schemas.  
**Warning signs:** Model repeatedly asks clarifying questions instead of calling tool.

## Testing Strategy (Planning-Critical)

- **Contract tests:** Validate every success/error response against Pydantic schemas.
- **Search reliability tests:** Retry on `429/5xx/network`, fail fast on permanent `4xx`.
- **Search normalization tests:** Trimmed query, normalized URLs, deterministic ranking.
- **Crawl reliability tests:** Network timeout/reset recovery, redirect handling, max-bytes guard.
- **Extraction tests:** HTML success, low-content-quality fallback, unsupported content type fallback.
- **Error observability tests:** Ensure `kind`, `retryable`, `attempt_number`, `operation`, and timings are present.
- **Golden-shape tests:** Snapshot minimal response objects for `web_search` and `web_crawl`.

## Code Examples

Verified patterns from official sources:

### Define tools with strict args schemas
```python
# Source: https://docs.langchain.com/oss/python/langchain/tools.md
from langchain.tools import tool
from pydantic import BaseModel, Field

class WebCrawlInput(BaseModel):
    url: str = Field(description="Absolute URL to crawl")

@tool("web_crawl", args_schema=WebCrawlInput)
def web_crawl(url: str) -> dict:
    return crawl_service(url)
```

### Bind tools for model tool-calling
```python
# Source: https://docs.langchain.com/oss/python/langchain/models#tool-calling
model_with_tools = model.bind_tools([web_search, web_crawl])
ai_msg = model_with_tools.invoke([{"role": "user", "content": "Find and summarize X"}])
for tool_call in ai_msg.tool_calls:
    ...
```

### Parse robots policy in Python stdlib
```python
# Source: https://docs.python.org/3/library/urllib.robotparser.html
import urllib.robotparser

rp = urllib.robotparser.RobotFileParser()
rp.set_url("https://example.com/robots.txt")
rp.read()
allowed = rp.can_fetch("web-agent-bot", "https://example.com/article")
delay = rp.crawl_delay("web-agent-bot")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Ad-hoc "function calling" payload handling per provider | Provider-agnostic tool interface via `bind_tools` and `tool_calls` | LangChain v1-era docs | Easier multi-provider portability, less custom glue code |
| Hand-built extraction pipelines with brittle selectors | Purpose-built extraction engines (Trafilatura) with markdown/text output | Mature ecosystem by 2025-2026 | Faster implementation, better extraction consistency |
| Unstructured exception strings | Typed, schema-validated error envelopes | Modern agent reliability patterns | Better debugging and safer planner assumptions |

**Deprecated/outdated:**
- `trafilatura` parameter `no_fallback`: marked deprecated; use `fast` instead.
- Phase-level assumption that tool failures can be represented as empty values: outdated; use explicit error/fallback states.

## Open Questions

1. **Should Phase 02 include robots gate now or defer to later safety phase?**
   - What we know: Python stdlib supports robots parsing now; TS codebase already treats compliance as explicit preflight.
   - What's unclear: Whether roadmap intends compliance in this phase or later.
   - Recommendation: Implement minimal `can_fetch` + optional `crawl_delay` now (small effort, high safety value).

2. **Tool failure channel: raise exceptions vs always return error objects?**
   - What we know: LangGraph `ToolNode` supports tool error handling; both approaches are viable.
   - What's unclear: Preferred runtime behavior for UI/logging in this repo.
   - Recommendation: Return contract-valid error objects from tools (not silent catches), and log/trace raw exceptions internally.

3. **Extraction quality threshold default**
   - What we know: Existing TS logic uses minimum text-length threshold to flag low quality.
   - What's unclear: Exact threshold desired for Python v1 behavior.
   - Recommendation: Start with deterministic baseline (e.g., 120 chars) and tune with fixtures.

## Sources

### Primary (HIGH confidence)
- [LangGraph quickstart](https://docs.langchain.com/oss/python/langgraph/quickstart.md) - Tool loop architecture, bind/execute flow
- [LangChain tools](https://docs.langchain.com/oss/python/langchain/tools.md) - `@tool`, args schema, ToolNode and error handling
- [LangChain models tool-calling](https://docs.langchain.com/oss/python/langchain/models#tool-calling) - `bind_tools`, `tool_calls`, parallel tool calls
- [Pydantic docs](https://docs.pydantic.dev/latest/) - Current version and validation patterns
- [HTTPX quickstart](https://www.python-httpx.org/quickstart/) - Request/timeout/error primitives
- [Tenacity docs](https://tenacity.readthedocs.io/en/latest/) - Retry policy primitives
- [Trafilatura docs](https://trafilatura.readthedocs.io/en/latest/corefunctions.html#extract) - Extraction API, markdown support, return behavior
- [urllib.robotparser docs](https://docs.python.org/3/library/urllib.robotparser.html) - Standard robots parsing APIs

### Secondary (MEDIUM confidence)
- [Serper homepage](https://serper.dev/) - Response shape examples and product-level behavior
- Existing repository TypeScript source/tests under `src/providers/serper`, `src/scraper`, `src/tests` - Proven normalization/error/reliability contract patterns to preserve in Python

### Tertiary (LOW confidence)
- Web search snippets for Serper endpoint docs discovery (sparse official endpoint docs surfaced via search in this environment)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Mostly official documentation with clear APIs and versions
- Architecture: HIGH - Aligned across official LangChain/LangGraph docs and existing repo patterns
- Pitfalls: HIGH - Derived from explicit reliability/extraction/tool-call failure modes in current codebase and docs

**Research date:** 2026-03-17  
**Valid until:** 2026-04-16 (30 days)
