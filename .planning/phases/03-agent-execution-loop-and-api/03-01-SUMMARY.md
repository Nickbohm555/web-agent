---
phase: 03-agent-execution-loop-and-api
plan: 01
subsystem: backend-agent-runtime
tags:
  - python
  - langchain
  - langgraph
  - openai
  - pydantic
  - pytest
requires:
  - 02-01-implement-serper-backed-web-search-tool-in-python
  - 02-02-implement-in-house-python-web-crawl-extraction-flow
provides:
  - single-run agent runtime facade with canonical `web_search` and `web_crawl` binding
  - normalized internal `AgentRunResult` and `AgentRunError` envelopes for downstream API mapping
  - bounded execution via recursion limits and stop-oriented system instructions
  - deterministic runtime failure categorization for invalid prompt, loop limit, tool, provider, timeout, and internal errors
  - regression coverage for successful runs, canonical tool binding, and typed failure paths
affects:
  - backend/agent/prompts.py
  - backend/agent/runtime.py
  - backend/agent/types.py
  - backend/tests/agent/test_runtime.py
tech-stack:
  added: []
  patterns:
    - runtime facade isolation between LangGraph execution and HTTP transport
    - canonical tool-name assertion to prevent drift from Phase 2 tool contracts
    - normalized provider-agnostic run result mapping
    - bounded recursion guard with typed runtime error mapping
key-files:
  created:
    - backend/agent/prompts.py
    - backend/agent/runtime.py
    - backend/agent/types.py
    - backend/tests/agent/test_runtime.py
  modified: []
key-decisions:
  - Bind exactly `web_search` and `web_crawl` and fail fast if tool decorator names drift from those canonical contracts.
  - Keep LangChain and provider payloads internal by returning only normalized run metadata and final-answer fields.
  - Treat loop-limit, timeout, tool, provider, and invalid-input failures as explicit runtime categories before the API layer exists.
duration: unknown
completed: 2026-03-17
---

# Phase 03 Plan 01: Agent Execution Loop and API Summary

Delivered a bounded backend agent runtime that executes one prompt with the Phase 2 search and crawl tools and returns a normalized internal result envelope ready for API transport.

## Outcome

Task 1 (`0815a3b`) created the runtime seam in [backend/agent/runtime.py](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/agent/runtime.py), the tool-usage instructions in [backend/agent/prompts.py](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/agent/prompts.py), the normalized result models in [backend/agent/types.py](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/agent/types.py), and the initial regression coverage in [backend/tests/agent/test_runtime.py](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/tests/agent/test_runtime.py). The runtime now builds a single-run agent facade, binds exactly the `web_search` and `web_crawl` tools, asserts their canonical names at startup, and maps raw runtime output into a provider-agnostic `AgentRunResult` with `run_id`, `status`, `final_answer`, `tool_call_count`, and `elapsed_ms`.

Task 2 (`ff3bb2b`) extended [backend/agent/runtime.py](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/agent/runtime.py), [backend/agent/prompts.py](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/agent/prompts.py), [backend/agent/types.py](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/agent/types.py), and [backend/tests/agent/test_runtime.py](/Users/nickbohm/Desktop/Tinkering/web-agent/backend/tests/agent/test_runtime.py) to enforce bounded execution and typed failures. Runs now invoke the agent with `recursion_limit=12`, the system prompt tells the model to stop once it has enough evidence, and known failure modes are normalized into explicit categories: `invalid_prompt`, `loop_limit`, `tool_failure`, `provider_failure`, `timeout`, and `internal_error`.

## Verification

Recorded outcomes from this iteration:
- `npm install` completed successfully.
- `npm run typecheck` completed successfully.
- `npm run test` passed with `19` test files and `104` tests passing.
- `npm run build` completed successfully.
- `pytest backend/tests/agent/test_runtime.py -q` passed with `8` tests.

## Commit Traceability

- `03-01-task1` (`0815a3b`): created the runtime facade, prompt instructions, normalized result models, and initial runtime tests.
- `03-01-task2` (`ff3bb2b`): added recursion bounding, stop-strategy guidance, typed runtime error mapping, and failure-path coverage.

## Deviations

The plan executed as written. No scope deviations were required.
