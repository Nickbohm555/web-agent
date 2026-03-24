# Parallel Fan-Out Web Crawl Design

Date: 2026-03-23
Status: Approved in chat

## Goal

Preserve the current two-tool research pattern:

- `web_search` to gather candidate URLs and snippets
- `web_crawl` to open pages and read their contents

while adding guaranteed parallel fan-out for page reads so the LLM can choose multiple promising URLs from search results and open them concurrently with deterministic backend behavior.

## Motivation

The current runtime already lets the model inspect search snippets and decide which pages are worth reading. That matches the desired interaction model. The gap is execution: page reads are currently modeled as one `web_crawl` call per URL, which leaves concurrency up to agent behavior instead of backend guarantees.

For speed-sensitive search flows, prompt-level encouragement is not enough. We need a tool contract that guarantees concurrent reads when the model selects more than one URL.

This keeps the product behavior close to the Onyx-style pattern described in "Building an Internet Search to rival OpenAI": search returns snippets and URLs, then the model chooses what to open next.

## Non-Goals

- Do not replace `web_search`.
- Do not add backend auto-selection of pages beyond what the model explicitly chooses.
- Do not redesign the extraction pipeline for a single page.
- Do not depend on the agent framework making parallel tool calls on its own.

## Desired User-Visible Behavior

The agent should:

1. Call `web_search` to get titles, snippets, and URLs.
2. Read the candidate list and decide which URLs are worth opening.
3. Call `web_crawl` once with multiple chosen URLs when it wants to inspect several pages.
4. Receive one structured batch result containing successful pages and per-URL failures.

This preserves the "the LLM chose what to read" property while making the actual page reads parallel and faster.

## Recommended Approach

Extend `web_crawl` so it supports both single-URL and multi-URL input.

Recommended input contract:

- `url: str | None`
- `urls: list[str] | None`
- `objective: str | None`

Validation rules:

- Exactly one of `url` or `urls` must be provided.
- `urls` must be non-empty and bounded by a hard cap.
- Every URL must be absolute `http` or `https`.
- Every URL must pass retrieval-policy domain checks before fetch.

This preserves backward compatibility while giving the runtime a deterministic fan-out path.

## Why This Approach

### Compared with prompt-only parallelism

Prompt-only guidance may encourage the model to issue multiple `web_crawl` calls in one turn, but it does not guarantee parallel execution and does not provide a clean batch result shape. It is too opportunistic for a speed-critical requirement.

### Compared with a new `web_open_many` tool

A separate batch tool would work technically, but it adds another tool concept and drifts away from the current two-tool mental model. Extending `web_crawl` keeps the public interaction simple: search, then open.

## Proposed Runtime Contract

### Single-page mode

Existing behavior remains:

- fetch one URL
- extract text, markdown, and excerpts
- return typed success or typed error

### Batch mode

When `urls` is provided:

- validate the full batch
- filter or reject URLs outside policy scope before fetch
- fetch and extract pages concurrently
- preserve partial success
- return one typed batch success envelope unless the request itself is invalid

The backend should not reorder the user-selected URLs unless there is a strong implementation reason. Input order should remain observable in the result.

## Proposed Schemas

New schema files should live under `backend/app/tools/schemas/` and remain category-focused.

Recommended additions:

- `web_crawl_batch.py`
- optionally a shared per-URL result model if it improves reuse

Recommended models:

- `WebCrawlBatchInput`
- `WebCrawlBatchItemSuccess`
- `WebCrawlBatchItemError`
- `WebCrawlBatchSuccess`

Suggested shape:

```json
{
  "requested_urls": [
    "https://example.com/a",
    "https://example.com/b"
  ],
  "results": [
    {
      "url": "https://example.com/a",
      "final_url": "https://example.com/a",
      "status_code": 200,
      "content_type": "text/html",
      "text": "...",
      "markdown": "...",
      "objective": null,
      "excerpts": [...]
    }
  ],
  "failures": [
    {
      "url": "https://example.com/b",
      "error": {
        "kind": "provider_timeout",
        "message": "request timed out",
        "retryable": true,
        "status_code": 504,
        "attempt_number": 1,
        "operation": "web_crawl",
        "timings": {
          "total_ms": 2000
        }
      }
    }
  ],
  "meta": {
    "operation": "web_crawl",
    "attempts": 1,
    "retries": 0,
    "duration_ms": 2100,
    "timings": {
      "total_ms": 2100
    }
  }
}
```

The batch response should also include aggregate counts such as attempted, succeeded, and failed if that proves useful for downstream reasoning or observability.

## Execution Design

To keep runtime paths explicit and files focused, batch orchestration should be split into small modules rather than added directly into one large `web_crawl.py` file.

Recommended responsibility split:

- `backend/app/tools/web_crawl.py`
  - tool entrypoint
  - single-vs-batch dispatch
  - policy checks at the tool boundary
- `backend/app/tools/web_crawl_batch.py`
  - batch orchestration
  - concurrency control
  - result aggregation
- `backend/app/tools/schemas/web_crawl_batch.py`
  - batch request/response models
- existing crawler modules
  - continue doing per-page fetch and extraction

### Concurrency model

The batch implementation should use a direct, explicit concurrency primitive and avoid generic runtime indirection.

Requirements:

- bounded concurrency
- deterministic timeout handling
- partial-failure tolerance
- straightforward mapping from per-URL execution to per-URL result

The exact primitive can follow what best fits the existing fetch worker implementation, but the path should remain explicit and testable.

## Policy and Safety Rules

Every selected URL must still respect the retrieval policy.

Batch behavior should:

- validate each URL before fetch
- either reject invalid requests up front or surface per-URL invalid-request failures consistently
- keep domain scoping behavior aligned with existing `web_crawl`
- preserve existing content-size truncation behavior per successful page where needed

The tool should enforce a hard upper bound on batch size to protect latency, provider load, and context growth.

## Prompt Changes

The system prompt should be updated so the agent is explicitly instructed to:

- use `web_search` to shortlist candidate URLs
- decide what to open from titles and snippets
- call `web_crawl` with multiple selected URLs in one call when several pages appear worth reading
- avoid serialized one-by-one crawling unless it must branch after reading an earlier page

This keeps the LLM in charge of selection while making the backend responsible for guaranteed fan-out.

## Observability

The runtime should preserve visibility into what happened during batch reads.

Minimum needs:

- which URLs were requested
- which succeeded
- which failed and why
- total batch timing

If action tracing is used downstream, batch crawl summaries should remain compact and avoid flooding logs with full extracted content.

## Testing Strategy

Add focused tests for:

- batch input validation
- backward compatibility for single-URL input
- mixed success and failure in one batch
- domain-scope enforcement for every URL
- bounded fan-out and concurrency behavior using stub fetch workers
- response schema validation for batch success and batch item failures
- updated prompt guidance encouraging batch page opens

If feasible, include a test that demonstrates the batch path completes faster than serial execution under controlled stub latency, or at minimum validates overlapping execution behavior.

## Rollout Plan

Phase 1:

- add batch schemas
- add batch execution module
- extend `web_crawl` entrypoint to accept `urls`
- keep single-URL behavior untouched

Phase 2:

- update prompt guidance for search-then-batch-open behavior
- add runtime and tool tests

Phase 3:

- inspect traces and adjust batch-size defaults or prompt wording if the model still underuses fan-out

## Open Questions

- Should invalid URLs inside a batch fail the whole request or become per-item failures?
- Should batch results preserve input order, completion order, or a normalized stable order?
- Should aggregate counts live inside `meta` or a separate summary object?

Current recommendation:

- invalid URL format should fail the request during validation
- policy-blocked URLs should surface as per-item failures only if mixed batches are valuable; otherwise reject up front for simplicity
- preserve input order in both requested URLs and result reporting

## Final Recommendation

Implement guaranteed parallel fan-out by extending `web_crawl` to support batch input while preserving the current two-tool pattern.

This gives the LLM the exact role we want:

- `web_search` shows the menu
- the LLM chooses what to read
- `web_crawl` opens the chosen pages in parallel

That is the closest fit to the desired behavior, the strongest answer to the speed requirement, and the cleanest evolution of the current architecture.
