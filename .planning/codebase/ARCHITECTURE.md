# Architecture

**Analysis Date:** 2026-03-24

## Pattern Overview

**Overall:** Dual-surface web retrieval system with a TypeScript local retrieval/UI server and a Python agent runtime/API.

**Key Characteristics:**
- The repository runs two application surfaces in parallel: the FastAPI backend in `backend/main.py` and the Express frontend server in `src/frontend/server.ts`.
- Retrieval logic exists in two stacks: TypeScript SDK/scraper code under `src/sdk/` and `src/scraper/`, plus Python LangChain tool/crawler code under `backend/app/tools/` and `backend/app/crawler/`.
- Mode handling is explicit. The Python agent runtime branches by `quick`, `agentic`, or `deep_research` in `backend/agent/runtime_execution.py`, while the browser and Express server treat mode as a UI/API contract in `src/frontend/contracts.ts` and `src/frontend/routes/runs.ts`.

## Layers

**Browser UI Layer:**
- Purpose: Render the run form, live timeline, payload inspector, and run history view.
- Location: `src/frontend/client/`
- Contains: DOM wiring in `src/frontend/client/app.ts`, client-side state reducer in `src/frontend/client/state.ts`, event rendering helpers in `src/frontend/client/timeline.ts` and `src/frontend/client/answer-rendering.ts`, and browser API access in `src/frontend/client/api-client.ts`.
- Depends on: Shared Zod contracts in `src/frontend/contracts.ts` and `src/frontend/client/browser-contracts.ts`.
- Used by: `public/index.html`, which loads browser modules served by `src/frontend/server.ts`.

**Frontend HTTP Layer:**
- Purpose: Serve the browser app and expose local HTTP endpoints for search, fetch, run start/streaming, and run history.
- Location: `src/frontend/server.ts` and `src/frontend/routes/`
- Contains: Route composition in `src/frontend/server.ts`, request parsing and envelope shaping in `src/frontend/contracts.ts`, and route handlers in `src/frontend/routes/search.ts`, `src/frontend/routes/fetch.ts`, `src/frontend/routes/runs.ts`, and `src/frontend/routes/run-history.ts`.
- Depends on: TypeScript SDK entrypoints in `src/sdk/search.ts` and `src/sdk/fetch.ts`, run history storage in `src/frontend/run-history/store.ts`, telemetry helpers in `src/core/telemetry/`.
- Used by: The browser UI and, when `AGENT_BACKEND_ORIGIN` is set, the Python backend via the HTTP run executor created in `src/frontend/routes/runs.ts`.

**TypeScript SDK Layer:**
- Purpose: Provide normalized `search()` and `fetch()` primitives with typed contracts, retry/caching, and policy enforcement.
- Location: `src/sdk/`
- Contains: Public entrypoints in `src/sdk/search.ts`, `src/sdk/fetch.ts`, and exported contracts in `src/sdk/contracts/`.
- Depends on: Provider adapters in `src/providers/serper/`, scraper orchestration in `src/scraper/orchestrator.ts`, cache/policy/network helpers in `src/core/`.
- Used by: Frontend routes in `src/frontend/routes/search.ts` and `src/frontend/routes/fetch.ts`.

**TypeScript Retrieval Infrastructure Layer:**
- Purpose: Execute safe outbound search/fetch calls and normalize content.
- Location: `src/providers/`, `src/scraper/`, and `src/core/`
- Contains: Serper HTTP client and mapping in `src/providers/serper/client.ts` and `src/providers/serper/mapper.ts`; fetch orchestration in `src/scraper/orchestrator.ts`; HTTP worker in `src/scraper/http-worker.ts`; extraction in `src/scraper/extract.ts`; SSRF, redirect, robots, retry, telemetry, and policy logic in `src/core/`.
- Depends on: External network services and local contract modules.
- Used by: `src/sdk/search.ts` and `src/sdk/fetch.ts`.

**Backend API Layer:**
- Purpose: Expose the agent run endpoint and map runtime results to HTTP responses.
- Location: `backend/main.py`, `backend/api/routes/agent_run.py`, `backend/api/services/agent_run.py`, `backend/api/schemas/agent_run.py`, and `backend/api/errors.py`
- Contains: FastAPI app bootstrapping, request/response schemas, service dispatch, and runtime-to-HTTP error mapping.
- Depends on: Agent runtime modules in `backend/agent/`.
- Used by: The frontend run executor in `src/frontend/routes/runs.ts` when the Express app is configured with `AGENT_BACKEND_ORIGIN`.

**Backend Agent Runtime Layer:**
- Purpose: Execute agent modes, build prompts/tools, infer retrieval policy, and normalize raw agent outputs into `AgentRunResult`.
- Location: `backend/agent/`
- Contains: Runtime branching and dependency assembly in `backend/agent/runtime_execution.py`, prompt building in `backend/agent/prompts.py`, quick deterministic flow in `backend/agent/quick_runtime.py`, deep-research queue/job flow in `backend/agent/deep_research_runtime.py`, and output/error helpers in `backend/agent/runtime_sources.py` and `backend/agent/runtime_errors.py`.
- Depends on: Backend tools in `backend/app/tools/`, LangChain/LangGraph/OpenAI packages, and schemas in `backend/agent/schemas/`.
- Used by: `backend/api/services/agent_run.py`.

**Backend Tool and Crawl Layer:**
- Purpose: Implement `web_search` and `web_crawl` as typed runtime tools plus lower-level crawler orchestration.
- Location: `backend/app/tools/`, `backend/app/providers/`, and `backend/app/crawler/`
- Contains: LangChain tool wrappers in `backend/app/tools/web_search.py` and `backend/app/tools/web_crawl.py`; Pydantic tool payloads in `backend/app/tools/schemas/`; Serper integration in `backend/app/providers/serper_client.py`; HTTP/browser crawl orchestration in `backend/app/crawler/fetch_orchestrator.py` with supporting workers, strategy, normalization, extraction, and session-profile modules.
- Depends on: `backend/app/config.py` for settings, `backend/app/core/retry.py`, and the crawler/tool schema packages.
- Used by: The agent runtime in `backend/agent/runtime_execution.py` and `backend/agent/quick_runtime.py`.

## Data Flow

**Frontend Search Flow:**

1. `src/frontend/routes/search.ts` parses the request with `parseSearchApiRequest()` from `src/frontend/contracts.ts`.
2. The route calls `search()` in `src/sdk/search.ts`.
3. `src/sdk/search.ts` calls `callSerperSearch()` in `src/providers/serper/client.ts`, maps provider payloads with `src/providers/serper/mapper.ts`, filters by domain scope, and returns a normalized SDK response.
4. `src/frontend/routes/search.ts` wraps the SDK result in a frontend envelope and emits telemetry through `src/core/telemetry/observability-logger.ts`.

**Frontend Fetch Flow:**

1. `src/frontend/routes/fetch.ts` validates input through `parseFetchApiRequest()` from `src/frontend/contracts.ts`.
2. The route calls `fetch()` in `src/sdk/fetch.ts`.
3. `src/sdk/fetch.ts` checks `src/core/cache/fetch-cache.ts` and falls through to `runFetchOrchestrator()` in `src/scraper/orchestrator.ts` on cache miss.
4. `src/scraper/orchestrator.ts` performs safety checks, DNS/IP classification, robots evaluation, HTTP fetch, and content extraction before returning a typed SDK response.

**Agent Run Flow:**

1. `backend/api/routes/agent_run.py` receives `POST /api/agent/run` and validates the body against `backend/api/schemas/agent_run.py`.
2. `backend/api/services/agent_run.py` dispatches by `payload.mode`.
3. For `quick` or `agentic`, the service calls `run_agent_once()` in `backend/agent/runtime_execution.py`.
4. `backend/agent/runtime_execution.py` resolves a runtime profile, merges inferred and explicit retrieval policy through `backend/agent/runtime_policy.py`, builds tools, and runs either `backend/agent/quick_runtime.py` or a LangChain/LangGraph executor.
5. Tool calls reach `backend/app/tools/web_search.py` and `backend/app/tools/web_crawl.py`, which delegate to `backend/app/providers/serper_client.py` and `backend/app/crawler/fetch_orchestrator.py`.
6. Raw agent output is normalized into `AgentRunResult` by `backend/agent/runtime_sources.py` and returned as `AgentRunSuccessResponse` or mapped error JSON.

**Deep Research Queue Flow:**

1. `backend/api/services/agent_run.py` calls `start_deep_research()` in `backend/agent/deep_research_runtime.py`.
2. `backend/agent/deep_research_runtime.py` saves a `DeepResearchJob` into the in-memory store in `backend/agent/deep_research_store.py` and returns `202 queued`.
3. Optional background work later runs `run_deep_research_job()`, which moves the job through planning, wave execution, verification, and finalization using `backend/agent/deep_research_planning.py`, `backend/agent/deep_research_execution.py`, and `backend/agent/deep_research_verification.py`.
4. The persisted deep-research store remains process-local because `backend/agent/deep_research_store.py` keeps jobs in an in-memory dictionary.

**Frontend Run Streaming Flow:**

1. The browser starts a run through `createRun()` in `src/frontend/client/api-client.ts`, which posts to `/api/runs`.
2. `src/frontend/routes/runs.ts` creates a local run record, writes initial history events into `src/frontend/run-history/store.ts`, and either starts a background run or exposes a stream factory.
3. The browser subscribes to `GET /api/runs/:runId/events` through `EventSource` in `src/frontend/client/api-client.ts`.
4. Server-side run events are parsed, stored, and replayed as SSE by `src/frontend/routes/runs.ts`, then reduced into browser state by `src/frontend/client/state.ts`.

**State Management:**
- Browser UI state is local reducer state in `src/frontend/client/state.ts`.
- Frontend server run history is in-memory process state created by `createRunHistoryStore()` in `src/frontend/run-history/store.ts`.
- Backend deep-research jobs are in-memory process state in `backend/agent/deep_research_store.py`.
- Retrieval request/response contracts are validated at boundaries with Zod in `src/frontend/contracts.ts` and Pydantic in `backend/api/schemas/agent_run.py`, `backend/agent/schemas/`, and `backend/app/tools/schemas/`.

## Runtime Modes

**Quick Mode:**
- Location: `backend/agent/quick_runtime.py`
- Triggers: `mode="quick"` in `backend/api/schemas/agent_run.py`
- Responsibilities: Run one deterministic search-first pipeline, select a few URLs, crawl them directly with `run_web_crawl()`, and optionally synthesize an answer with `backend/agent/answer_synthesis.py`.

**Agentic Mode:**
- Location: `backend/agent/runtime_execution.py`
- Triggers: `mode="agentic"`
- Responsibilities: Build a LangChain/LangGraph agent with bounded tool limits, execute the prompt as a tool-using loop, and post-process final answer and sources from raw runtime messages.

**Deep Research Mode:**
- Location: `backend/api/services/agent_run.py`, `backend/agent/deep_research_runtime.py`, and `backend/agent/runtime_execution.py`
- Triggers: `mode="deep_research"`
- Responsibilities: At the HTTP layer, queue background work and return `202`; at runtime level, there is also a LangChain profile path in `backend/agent/runtime_execution.py` for deep-research execution configuration; at job orchestration level, `backend/agent/deep_research_runtime.py` manages staged research jobs.

## Key Abstractions

**AgentRunResult:**
- Purpose: Canonical backend output for all agent modes.
- Examples: `backend/agent/schemas/__init__.py`, `backend/api/schemas/agent_run.py`
- Pattern: The backend service layer always converts runtime work into `AgentRunResult`, then maps it to HTTP response models.

**AgentRunRetrievalPolicy:**
- Purpose: Shared retrieval constraints for freshness, domain scoping, and fetch freshness.
- Examples: `backend/agent/schemas/__init__.py`, `backend/agent/runtime_policy.py`, `src/core/policy/retrieval-controls.ts`, `src/frontend/contracts.ts`
- Pattern: Policy is inferred from prompts in Python and normalized from UI input in TypeScript, but the two stacks maintain separate schema implementations.

**RuntimeDependencies:**
- Purpose: Inject the specific seams used by the backend runtime for tests and mode switching.
- Examples: `backend/agent/runtime_execution.py`
- Pattern: Concrete runtime code calls direct functions by default and only injects narrow dependencies such as search runners, crawl runners, agent executors, or deep-research runners.

**WebSearchToolResult / WebCrawlToolResult:**
- Purpose: Typed union payloads returned by backend tools.
- Examples: `backend/app/tools/schemas/web_search.py`, `backend/app/tools/schemas/web_crawl.py`, `backend/app/tools/schemas/web_crawl_batch.py`
- Pattern: Tool wrappers return Pydantic-validated success or error envelopes rather than raw dicts.

**Run History Store:**
- Purpose: Persist a bounded event log for the frontend’s run inspector and history view.
- Examples: `src/frontend/run-history/store.ts`, `src/frontend/routes/run-history.ts`
- Pattern: The frontend server owns an in-memory append-only event store with truncation and retention limits.

## Entry Points

**Backend HTTP App:**
- Location: `backend/main.py`
- Triggers: `uvicorn backend.main:app` from `backend/Dockerfile`
- Responsibilities: Load settings into app state, mount the agent-run router, and expose `/healthz`.

**Backend Compatibility Import:**
- Location: `backend/app/main.py`
- Triggers: Alternate import path for the FastAPI app
- Responsibilities: Re-export `backend.main.app`.

**Frontend Server:**
- Location: `src/frontend/server.ts`
- Triggers: `npm run dev:frontend`, which runs `tsx src/frontend/server.ts`
- Responsibilities: Start Express, mount `/api` routers, provide health checks, transpile browser `.ts` modules on demand, serve `public/index.html`, and attach in-memory run history state.

**Browser App Bootstrap:**
- Location: `public/index.html`
- Triggers: Browser navigation to `/`
- Responsibilities: Provide the DOM shell and load the browser client modules served by `src/frontend/server.ts`.

## Error Handling

**Strategy:** Validate at each boundary, convert provider/runtime exceptions into typed envelopes, and surface mode-specific failures without leaking raw framework errors.

**Patterns:**
- Frontend routes map Zod and SDK errors into stable error envelopes in `src/frontend/contracts.ts`, `src/frontend/routes/search.ts`, and `src/frontend/routes/fetch.ts`.
- The TypeScript fetch path throws safety-aware SDK errors from `src/scraper/orchestrator.ts` and `src/core/errors/`.
- The backend runtime maps Python exceptions to `AgentRunResult(error=...)` through `backend/agent/runtime_errors.py`.
- The backend API converts failed `AgentRunResult` objects into HTTP status codes through `backend/api/errors.py`.
- Backend tools return typed `WebSearchError` and `WebCrawlError` models instead of raising most validation/provider errors from `backend/app/tools/web_search.py` and `backend/app/tools/web_crawl.py`.

## Cross-Cutting Concerns

**Logging:** TypeScript request/tool observability is emitted from `src/core/telemetry/observability-logger.ts`; TypeScript provider/HTTP workers use `pino` in `src/providers/serper/client.ts` and `src/scraper/http-worker.ts`; the Python backend currently emphasizes typed results over a centralized logger.

**Validation:** Zod is the contract layer in `src/frontend/contracts.ts` and `src/sdk/contracts/`; Pydantic is the contract layer in `backend/api/schemas/`, `backend/agent/schemas/`, `backend/app/tools/schemas/`, and `backend/app/crawler/schemas/`.

**Authentication:** External auth is limited to API keys loaded from environment in `backend/app/config.py` and `src/providers/serper/client.ts`. There is no end-user auth layer on either HTTP surface.

**Policy Enforcement:** Domain scoping and freshness are applied in Python through `backend/agent/runtime_policy.py` and `backend/app/tools/_tool_utils.py`, and in TypeScript through `src/core/policy/retrieval-controls.ts` and `src/providers/serper/search-result-filter.ts`.

---

*Architecture analysis: 2026-03-24*
