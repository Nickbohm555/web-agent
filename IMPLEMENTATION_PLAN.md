# Implementation Plan

This plan consolidates roadmap phases 1-5 into executable sections aligned to the active phase plans in `.planning/phases/`.

## Section 1: Local Compose Runtime Foundation - multi-service startup contract

**Single goal:** Establish one Docker Compose entrypoint that boots backend and frontend with deterministic startup order and required environment wiring.

**Details:**
- Create a root `docker-compose.yml` with `backend` and `frontend` services, explicit ports, and health-gated `depends_on`.
- Enforce required keys with Compose interpolation checks for `OPENAI_API_KEY` and `SERPER_API_KEY`.
- Add healthcheck probes so frontend startup is gated on backend readiness.
- Keep runtime local-first and avoid production-only orchestration complexity in this phase.

**Tech stack and dependencies**
- Libraries/packages: no new application libraries required for this section.
- Tooling: Docker Compose becomes the canonical local startup path; add/update `backend/Dockerfile` and `frontend/Dockerfile`.

**Files and purpose**

| File | Purpose |
|------|--------|
| `docker-compose.yml` | Defines backend/frontend services, env wiring, ports, and health/dependency semantics. |
| `backend/Dockerfile` | Provides reproducible backend container build for local runtime. |
| `frontend/Dockerfile` | Provides reproducible frontend container build for local runtime. |

**How to test:** Run `docker compose config` with and without required keys to verify failure/success behavior, then run `docker compose build backend frontend` to validate image build paths.

## Section 2: Backend Environment Validation - startup-time key enforcement

**Single goal:** Fail backend startup early when required provider keys are missing, and start cleanly when both keys are present.

**Details:**
- Introduce typed backend settings for required key fields and shared settings access helper.
- Validate configuration at app startup/lifespan, not lazily inside tool calls.
- Expose `/healthz` for runtime checks and Compose health probes.
- Add regression tests for missing-key failure paths and valid-key startup path.

**Tech stack and dependencies**
- Libraries/packages: add `pydantic-settings` in backend dependencies if missing.
- Tooling: re-use Docker Compose health checks to verify startup and reachability.

**Files and purpose**

| File | Purpose |
|------|--------|
| `backend/app/config.py` | Defines typed settings and key requirements. |
| `backend/app/main.py` | Wires startup validation and health endpoint. |
| `backend/requirements.txt` | Declares backend config dependency updates. |
| `backend/tests/test_startup_settings.py` | Protects required-key startup behavior with automated tests. |

**How to test:** Run `pytest backend/tests/test_startup_settings.py`, then verify Compose failure with missing keys and success with both keys exported.

## Section 3: Search Tool Capability - Serper-backed normalized web search

**Single goal:** Implement a reliable `web_search` tool that returns normalized results and explicit retry/error metadata.

**Details:**
- Define strict contracts for search input, normalized results, success envelope, and shared error envelope.
- Implement Serper provider client with bounded retry on transient failures and fail-fast behavior on terminal 4xx.
- Normalize provider output into stable fields (`title`, `url`, `snippet`, `rank`) and avoid leaking raw provider payload.
- Expose LangChain `@tool("web_search")` adapter with deterministic success/error return contracts.

**Tech stack and dependencies**
- Libraries/packages: ensure backend has `httpx`, `tenacity`, and `pydantic` for transport, retry, and validation.
- Tooling: no new container requirements in this section.

**Files and purpose**

| File | Purpose |
|------|--------|
| `backend/app/contracts/tool_errors.py` | Defines shared typed error envelope for tool failures. |
| `backend/app/contracts/web_search.py` | Defines request/response models for normalized search output. |
| `backend/app/core/retry.py` | Implements bounded retry policy and classification hooks. |
| `backend/app/providers/serper_client.py` | Calls Serper and maps provider data into normalized contracts. |
| `backend/app/tools/web_search.py` | Exposes canonical `web_search` tool adapter. |
| `backend/tests/tools/test_web_search_tool.py` | Validates contract shape, ranking stability, and retry/failure behavior. |
| `backend/requirements.txt` | Tracks backend dependency additions/updates for this path. |

**How to test:** Run `pytest backend/tests/tools/test_web_search_tool.py` and include mocked cases for 200, 429 retry recovery, 5xx failure, and 4xx fail-fast paths.

## Section 4: Crawl Tool Capability - HTTP-first content extraction

**Single goal:** Implement a stable `web_crawl` tool with explicit extraction states, fallback reasons, and structured error metadata.

**Details:**
- Define strict crawl contracts covering success payload, fallback reason, metadata, and error envelope.
- Build HTTP-first worker with timeout, redirect handling, content-type checks, and bounded retry on transient failures.
- Implement deterministic extraction flow that outputs markdown/text and maps low-quality or unsupported content to explicit fallback states.
- Expose LangChain `@tool("web_crawl")` adapter with stable contract output for success and failure.

**Tech stack and dependencies**
- Libraries/packages: ensure backend includes `trafilatura`, `httpx`, `tenacity`, and validation dependencies.
- Tooling: no new orchestration tools; this section is backend implementation/test focused.

**Files and purpose**

| File | Purpose |
|------|--------|
| `backend/app/contracts/web_crawl.py` | Defines crawl input/output and fallback/error schema contracts. |
| `backend/app/crawler/http_worker.py` | Performs HTTP-first retrieval with retry/error classification. |
| `backend/app/crawler/extractor.py` | Converts fetched content into deterministic text/markdown plus quality state. |
| `backend/app/tools/web_crawl.py` | Exposes canonical `web_crawl` tool adapter. |
| `backend/tests/tools/test_web_crawl_tool.py` | Covers success, redirects, fallback reasons, and structured error behavior. |
| `backend/requirements.txt` | Tracks backend dependency additions/updates for crawling path. |

**How to test:** Run `pytest backend/tests/tools/test_web_crawl_tool.py` with fixture/mocked cases for rich HTML, low-quality HTML, non-HTML content, redirects, and network failures.

## Section 5: Agent Runtime Loop - bounded ReAct orchestration

**Single goal:** Wire one bounded runtime entrypoint that can use `web_search` and `web_crawl` in sequence and return a normalized run result.

**Details:**
- Build runtime facade (for example `run_agent_once`) that binds only canonical tool names and executes one run per prompt.
- Add prompt instructions and loop-stop strategy for bounded agent behavior.
- Enforce explicit iteration/recursion limits and map runtime failures into typed internal categories.
- Return normalized internal run results (final answer + metadata) without exposing provider internals.

**Tech stack and dependencies**
- Libraries/packages: use existing LangGraph/LangChain backend stack already selected in phase research.
- Tooling: no additional container changes; this section is runtime orchestration logic.

**Files and purpose**

| File | Purpose |
|------|--------|
| `backend/agent/runtime.py` | Implements bounded agent execution and tool orchestration facade. |
| `backend/agent/prompts.py` | Defines system behavior constraints and stop strategy instructions. |
| `backend/agent/types.py` | Defines normalized runtime result and error categories for API mapping. |
| `backend/tests/agent/test_runtime.py` | Verifies direct-answer flow, tool-sequence flow, and bounded failure handling. |

**How to test:** Run `pytest backend/tests/agent/test_runtime.py -q` including normal, recursion-limit, and tool/runtime failure scenarios.

## Section 6: Agent Execution API - stable run endpoint contract

**Single goal:** Expose a frontend-callable run endpoint that executes one runtime call and returns a stable final-answer envelope.

**Details:**
- Define strict API request/response contracts and explicit typed error envelope.
- Implement `POST /api/agent/run` route that validates prompt input and calls runtime exactly once.
- Map runtime errors to deterministic HTTP status and machine-readable error codes.
- Keep response additive-safe with stable fields for frontend rendering (`run_id`, `status`, `final_answer`, `tool_call_count`, `elapsed_ms`).

**Tech stack and dependencies**
- Libraries/packages: no new packages required beyond existing FastAPI/Pydantic backend stack.
- Tooling: no Docker changes in this slice.

**Files and purpose**

| File | Purpose |
|------|--------|
| `backend/api/contracts.py` | Defines external request/response API models. |
| `backend/api/errors.py` | Maps runtime errors to stable HTTP/API error responses. |
| `backend/api/routes/agent_run.py` | Implements run endpoint orchestration and response shaping. |
| `backend/main.py` | Registers API route into backend application wiring. |
| `backend/tests/api/test_agent_run_route.py` | Verifies request validation, success contract, and error mapping behavior. |

**How to test:** Run `pytest backend/tests/api/test_agent_run_route.py -q` and one local smoke call to `POST /api/agent/run`.

## Section 7: Frontend Run Start Surface - prompt input and run initiation

**Single goal:** Deliver a minimal frontend UI where users enter a prompt, start a run, and observe initial state transitions.

**Details:**
- Add typed run-start contracts and route for `POST /api/runs` with strict validation.
- Implement minimal client API call and run-state reducer (`idle -> starting -> running|failed`).
- Build simple one-screen UI with prompt input, run trigger, and status region.
- Keep this section focused on run initiation; defer timeline details to next section.

**Tech stack and dependencies**
- Libraries/packages: use existing TypeScript, Express, and `zod` frontend stack.
- Tooling: no additional package manager or container changes required.

**Files and purpose**

| File | Purpose |
|------|--------|
| `src/frontend/contracts.ts` | Defines `POST /api/runs` request/response schemas and inferred types. |
| `src/frontend/routes/runs.ts` | Implements run-start API route contract and validation handling. |
| `src/frontend/server.ts` | Registers run route and server wiring. |
| `src/frontend/client/api-client.ts` | Sends typed run-start requests from browser UI. |
| `src/frontend/client/state.ts` | Manages run-phase transitions with reducer semantics. |
| `src/frontend/client/app.ts` | Connects UI events to API client and reducer updates. |
| `public/index.html` | Renders minimal prompt/run UI shell. |
| `src/tests/frontend-api/runs.contracts.test.ts` | Validates run-start route contract and malformed input behavior. |

**How to test:** Run `npm run test -- src/tests/frontend-api/runs.contracts.test.ts`, then manually submit valid/invalid prompts from the local UI.

## Section 8: Frontend Live Timeline - per-tool status and duration

**Single goal:** Show live tool-call progress with statuses and durations, and settle cleanly on terminal run events.

**Details:**
- Add typed SSE event schemas for run lifecycle and tool-call updates.
- Implement EventSource subscription lifecycle and parser/validation guards.
- Enforce idempotent reducer behavior keyed by `toolCallId` with monotonic run-state transitions.
- Render timeline rows with provisional duration while running and backend `durationMs` as final source of truth.

**Tech stack and dependencies**
- Libraries/packages: no new dependencies required beyond current frontend runtime and tests.
- Tooling: SSE subscription and cleanup behavior implemented in app/client code; no container updates.

**Files and purpose**

| File | Purpose |
|------|--------|
| `src/frontend/contracts.ts` | Adds typed run-event schemas including tool enums and duration fields. |
| `src/frontend/routes/runs.ts` | Exposes/aligns SSE event stream shape for run progress. |
| `src/frontend/client/api-client.ts` | Manages EventSource creation, parsing, and cleanup. |
| `src/frontend/client/state.ts` | Applies idempotent event updates and terminal-state guards. |
| `src/frontend/client/timeline.ts` | Maps state to timeline rows and duration formatting. |
| `src/frontend/client/app.ts` | Renders live timeline updates and terminal run state. |
| `public/index.html` | Hosts timeline render targets. |
| `src/tests/frontend/state.test.ts` | Verifies reducer ordering/dedupe/terminal invariants. |
| `src/tests/frontend/timeline.test.ts` | Verifies duration display logic and edge cases. |
| `src/tests/frontend-api/runs.stream.test.ts` | Verifies SSE contract handling and stream parsing behavior. |

**How to test:** Run `npm run test -- src/tests/frontend/state.test.ts src/tests/frontend/timeline.test.ts src/tests/frontend-api/runs.stream.test.ts` and manually confirm live timeline behavior from UI.

## Section 9: Canonical RunEvent + Payload Inspector - full tool I/O in UI

**Single goal:** Introduce one canonical run-event contract and UI payload inspector that shows full tool input/output with visible safety markers.

**Details:**
- Define canonical `RunEvent` schema with required correlation fields and payload slots.
- Include redaction and truncation metadata so payload policy decisions are explicit in UI.
- Render timeline selection and payload detail pane with ordered events by `event_seq`.
- Cover success and failure tool events so debugging remains complete across outcomes.

**Tech stack and dependencies**
- Libraries/packages: continue schema validation with existing `zod`; no new framework requirement.
- Tooling: browser-side rendering remains framework-agnostic and local-first.

**Files and purpose**

| File | Purpose |
|------|--------|
| `src/frontend/contracts/run-events.ts` | Defines canonical `RunEvent` schema/type for observability payloads. |
| `src/frontend/contracts.ts` | Re-exports run-event contract helpers for shared frontend use. |
| `public/index.html` | Hosts timeline + payload inspector layout. |
| `public/app.js` | Renders selected event payload input/output and safety indicators. |
| `src/tests/frontend-api/run-events.contracts.test.ts` | Validates schema acceptance/rejection and safety guardrail invariants. |

**How to test:** Run `npm run test -- src/tests/frontend-api/run-events.contracts.test.ts` and manually inspect one successful and one failed tool event in the payload inspector.

## Section 10: Structured Backend Observability - correlated logs and parity

**Single goal:** Emit structured backend events with `run_id` and `event_seq` so frontend timeline events can be correlated one-to-one with Docker logs.

**Details:**
- Add run-scoped async context initialization and monotonic sequence generation at run boundaries.
- Implement structured observability logger with redaction and payload truncation before emission.
- Instrument tool routes (`search`, `fetch`) with lifecycle events (`started`, `succeeded`, `failed`).
- Add parity tests matching UI and backend events on (`run_id`, `event_seq`, `event_type`).

**Tech stack and dependencies**
- Libraries/packages: use existing `pino` and Node `AsyncLocalStorage` primitives.
- Tooling: update `docker-compose.yml` backend logging configuration with JSON logs and rotation bounds.

**Files and purpose**

| File | Purpose |
|------|--------|
| `src/core/telemetry/run-context.ts` | Stores run-scoped context and event sequence generation. |
| `src/core/telemetry/observability-logger.ts` | Emits structured/redacted/truncated observability events. |
| `src/frontend/server.ts` | Initializes run context at request/run entrypoints. |
| `src/frontend/routes/search.ts` | Emits structured search tool lifecycle events. |
| `src/frontend/routes/fetch.ts` | Emits structured fetch tool lifecycle events. |
| `docker-compose.yml` | Configures backend Docker log driver/options for local retrieval. |
| `src/tests/frontend-api/observability-correlation.test.ts` | Ensures UI/log event parity and correlation invariants. |

**How to test:** Run `npm run test -- src/tests/frontend-api/observability-correlation.test.ts` and verify `docker compose logs --timestamps backend` includes structured correlated event records.

## Section 11: Cohesive Run History - final answer plus complete trace

**Single goal:** Provide one run-history flow where users can inspect final answer and full ordered tool trace for current and prior runs.

**Details:**
- Build bounded in-memory history store keyed by `run_id` with retention and payload limits.
- Preserve deterministic ordering by `event_seq` and handle duplicate/out-of-order records safely.
- Expose run-history list/detail APIs that return answer + ordered event trace in one response model.
- Finalize UI flow to select runs and inspect answer, timeline, and payload details on one screen.

**Tech stack and dependencies**
- Libraries/packages: no additional dependency required; implement with existing frontend/server stack.
- Tooling: no extra container tooling beyond logging already configured in Section 10.

**Files and purpose**

| File | Purpose |
|------|--------|
| `src/frontend/run-history/store.ts` | Stores bounded run snapshots with ordering and retention rules. |
| `src/frontend/routes/run-history.ts` | Serves run list and run detail endpoints for history inspection. |
| `src/frontend/server.ts` | Registers run-history routes into frontend server. |
| `public/index.html` | Hosts cohesive run detail interface regions. |
| `public/app.js` | Renders run selector, final answer, timeline, and payload inspector together. |
| `src/tests/frontend-api/run-history.integration.test.ts` | Verifies history contracts, ordering invariants, and bound enforcement. |

**How to test:** Run `npm run test -- src/tests/frontend-api/run-history.integration.test.ts` and manually verify a current run and a prior run both render answer + ordered trace in one view.
