---
phase: 02-search-and-crawl-tool-capability
plan: 02
subsystem: backend-crawl-tooling
tags:
  - python
  - langchain
  - httpx
  - tenacity
  - trafilatura
  - pytest
requires:
  - 02-01-implement-serper-backed-web-search-tool-in-python
provides:
  - strict crawl contracts for success payloads, fallback states, and shared tool errors
  - HTTP-first fetch worker with bounded retries, redirect capture, and content-type and size guardrails
  - deterministic Trafilatura extraction with explicit low-content and unsupported-content fallback reasons
  - LangChain `web_crawl` tool adapter with contract-valid success and error envelopes
  - regression coverage for crawl success, fallback, and retry/error metadata paths
affects:
  - backend/app/contracts/web_crawl.py
  - backend/app/crawler/http_worker.py
  - backend/app/crawler/extractor.py
  - backend/app/tools/web_crawl.py
  - backend/tests/crawler/test_http_worker.py
  - backend/tests/crawler/test_extractor.py
  - backend/tests/tools/test_web_crawl_tool.py
  - backend/requirements.txt
  - .planning/ROADMAP.md
  - .planning/STATE.md
tech-stack:
  added:
    - trafilatura
  patterns:
    - strict Pydantic v2 crawl contracts with shared tool-error envelopes
    - bounded retry classification for transient crawl transport failures
    - HTTP-first retrieval with explicit unsupported-content and response-size guardrails
    - deterministic extraction state mapping before tool response shaping
    - thin LangChain tool adapter over internal fetch and extraction services
key-files:
  created:
    - backend/app/contracts/web_crawl.py
    - backend/app/crawler/__init__.py
    - backend/app/crawler/http_worker.py
    - backend/app/crawler/extractor.py
    - backend/app/tools/web_crawl.py
    - backend/tests/crawler/__init__.py
    - backend/tests/crawler/test_http_worker.py
    - backend/tests/crawler/test_extractor.py
    - backend/tests/tools/test_web_crawl_tool.py
  modified:
    - backend/app/tools/__init__.py
    - backend/requirements.txt
    - .planning/ROADMAP.md
    - .planning/STATE.md
key-decisions:
  - Treat unsupported content types as explicit fallback success payloads instead of opaque transport failures.
  - Enforce a deterministic extracted-text threshold so low-value pages never appear as silent successful crawls.
  - Preserve shared tool error semantics from Plan 02-01 so search and crawl failures expose the same debugging fields.
  - Keep the tool surface as `web_crawl` with strict args validation and normalized output fields only.
duration: unknown
completed: 2026-03-17
---

# Phase 02 Plan 02: Implement In-House Python Web Crawl Extraction Flow Summary

Delivered a contract-first Python `web_crawl` tool that fetches pages over HTTP, extracts main content deterministically, and surfaces explicit fallback or error states instead of silent empty results.

## Outcome

Task 1 (`7dbf3cf`) added crawl contracts in [backend/app/contracts/web_crawl.py](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/app/contracts/web_crawl.py), the HTTP worker in [backend/app/crawler/http_worker.py](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/app/crawler/http_worker.py), and regression coverage in [backend/tests/crawler/test_http_worker.py](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/tests/crawler/test_http_worker.py). The fetch path now retries transient transport and retryable HTTP failures with bounded attempts, preserves redirect final URLs, rejects unsupported content types explicitly, and enforces response-size guardrails before extraction.

Task 2 (`150effc`) added deterministic extraction logic in [backend/app/crawler/extractor.py](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/app/crawler/extractor.py), extended the crawl contract in [backend/app/contracts/web_crawl.py](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/app/contracts/web_crawl.py), and added focused extraction tests in [backend/tests/crawler/test_extractor.py](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/tests/crawler/test_extractor.py). Extraction now emits explicit `ok`, `low-content-quality`, `unsupported-content-type`, and `network-error` states, with low-quality pages mapped to a stable `fallback_reason` instead of nominal success with empty content.

Task 3 (`8188ac4`) added the LangChain adapter in [backend/app/tools/web_crawl.py](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/app/tools/web_crawl.py), exported it through [backend/app/tools/__init__.py](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/app/tools/__init__.py), and completed tool-level regression coverage in [backend/tests/tools/test_web_crawl_tool.py](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/tests/tools/test_web_crawl_tool.py). The tool is exposed as `web_crawl`, validates strict args, and returns either a contract-valid crawl success payload or a shared structured error envelope with retry and timing metadata.

## Verification

Recorded execution outcomes:
- `npm install` completed successfully.
- `npm run typecheck` completed successfully.
- `npm run test` passed with `19` test files and `104` tests passing.
- `npm run build` completed successfully.
- `pytest backend/tests -q` passed with `44` tests.

## Phase Completion Update

[`.planning/ROADMAP.md`](/Users/nickbohm/Desktop/Tinkering/web-agent/.planning/ROADMAP.md) now marks Phase 2 and both of its plans complete. [`.planning/STATE.md`](/Users/nickbohm/Desktop/Tinkering/web-agent/.planning/STATE.md) advances the active focus to Phase 3, Plan 01 (`03-01`).

## Commit Traceability

- `02-02-task1` (`7dbf3cf`): created the crawl contract layer, HTTP worker, and fetch-path regression coverage.
- `02-02-task2` (`150effc`): added deterministic extraction state handling and extraction-focused tests.
- `02-02-task3` (`8188ac4`): added the LangChain `web_crawl` adapter and finalized contract-level tool coverage.

## Deviations

The plan executed as written. No scope or behavior deviations were required beyond rerunning the documented repository validation sequence to confirm the phase remains green at summary time.
