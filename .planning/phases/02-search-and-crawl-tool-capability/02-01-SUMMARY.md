---
phase: 02-search-and-crawl-tool-capability
plan: 01
subsystem: backend-search-tooling
tags:
  - python
  - langchain
  - serper
  - httpx
  - tenacity
  - pytest
requires:
  - 01-02-implement-environment-configuration-loading-and-startup-validation
provides:
  - strict Pydantic contracts for normalized search outputs and shared tool errors
  - bounded retrying Serper client with deterministic normalization
  - LangChain `web_search` tool adapter with contract-valid success and error envelopes
  - regression coverage for ranking, retries, and explicit failure semantics
affects:
  - backend/app/contracts/tool_errors.py
  - backend/app/contracts/web_search.py
  - backend/app/core/retry.py
  - backend/app/providers/serper_client.py
  - backend/app/tools/web_search.py
  - backend/tests/tools/test_web_search_tool.py
  - backend/requirements.txt
tech-stack:
  added:
    - tenacity
  patterns:
    - strict Pydantic v2 contracts for tool args and result envelopes
    - bounded retry classification for transient Serper and network failures
    - provider-to-contract normalization before tool return
    - thin LangChain tool adapter over internal provider client
key-files:
  created:
    - backend/app/contracts/__init__.py
    - backend/app/contracts/tool_errors.py
    - backend/app/contracts/web_search.py
    - backend/app/core/__init__.py
    - backend/app/core/retry.py
    - backend/app/providers/__init__.py
    - backend/app/providers/serper_client.py
    - backend/app/tools/__init__.py
    - backend/app/tools/web_search.py
  modified:
    - backend/tests/tools/test_web_search_tool.py
    - backend/requirements.txt
key-decisions:
  - Keep Serper payload details internal and return only normalized search result fields.
  - Retry only transient conditions with bounded attempts and expose attempt metadata in failures.
  - Return explicit structured error envelopes instead of silent empty result sets.
  - Expose the tool as `web_search` with a strict args schema so later agent orchestration can call it without adapter glue.
duration: unknown
completed: 2026-03-17
---

# Phase 02 Plan 01: Implement Serper-Backed Web Search Tool in Python Summary

Delivered a contract-first Python `web_search` tool that normalizes Serper results, retries transient failures, and surfaces explicit machine-readable errors.

## Outcome

Task 1 (`c243735`) added the shared error and search contracts in [backend/app/contracts/tool_errors.py](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/app/contracts/tool_errors.py) and [backend/app/contracts/web_search.py](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/app/contracts/web_search.py). The outward contract now fixes the public result shape to `title`, `url`, `snippet`, and `rank`, with explicit metadata and reusable structured tool-error models.

Task 2 (`e07d939`) added the retry utility in [backend/app/core/retry.py](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/app/core/retry.py), the Serper transport and mapper in [backend/app/providers/serper_client.py](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/app/providers/serper_client.py), and the required dependency in [backend/requirements.txt](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/requirements.txt). The provider path now retries transient `httpx` and retryable HTTP failures with bounded attempts, fails fast on non-retryable 4xx responses, and maps provider ordering into deterministic rank positions.

Task 3 (`e92a4fe`) added the LangChain adapter in [backend/app/tools/web_search.py](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/app/tools/web_search.py) and completed the regression suite in [backend/tests/tools/test_web_search_tool.py](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/tests/tools/test_web_search_tool.py). The tool is exported as `web_search`, validates strict args, and always returns either a contract-valid success envelope or a contract-valid error envelope with debuggable failure fields.

## Verification

Recorded execution evidence:
- `pytest backend/tests/tools/test_web_search_tool.py` passed during task execution coverage work.
- `npm install` completed successfully in this summary iteration.
- `npm run typecheck` completed successfully in this summary iteration.
- `npm run test` passed with `19` test files and `104` tests passing in this summary iteration.
- `npm run build` completed successfully in this summary iteration.
- `pytest backend/tests -q` passed with `25` tests in this summary iteration.

## Commit Traceability

- `02-01-task1` (`c243735`): created the search and error contract layer and seeded initial tool contract tests.
- `02-01-task2` (`e07d939`): added retry infrastructure, Serper client transport, normalization logic, and expanded provider reliability coverage.
- `02-01-task3` (`e92a4fe`): added the LangChain `web_search` adapter and finalized success/error envelope assertions.

## Deviations

The plan executed as written. No scope or behavior deviations were required beyond rerunning the current repository validation sequence to confirm the plan remains green at summary time.
