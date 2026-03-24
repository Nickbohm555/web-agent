# Codebase Structure

**Analysis Date:** 2026-03-24

## Directory Layout

```text
web-agent/
├── backend/                 # Python FastAPI app, agent runtime, LangChain tools, crawler, and pytest suite
├── frontend/                # Frontend container build context only (`frontend/Dockerfile`)
├── public/                  # Static browser shell served by Express
├── src/                     # TypeScript retrieval SDK, Express frontend server, browser client, and Vitest tests
├── dist/                    # Built TypeScript output from `npm run build`
├── docs/                    # Additional project documents
├── .planning/               # GSD planning state and codebase mapping output
├── docker-compose.yml       # Local two-service runtime wiring
├── package.json             # TypeScript package scripts and dependencies
└── README.md                # Minimal repo overview
```

## Directory Purposes

**`backend/`:**
- Purpose: Python application surface for the agent API and runtime.
- Contains: FastAPI app entrypoints, agent runtime modules, API schemas/routes/services, LangChain tools, crawler modules, and backend tests.
- Key files: `backend/main.py`, `backend/api/routes/agent_run.py`, `backend/agent/runtime_execution.py`, `backend/app/tools/web_search.py`, `backend/app/tools/web_crawl.py`, `backend/app/crawler/fetch_orchestrator.py`, `backend/requirements.txt`

**`backend/agent/`:**
- Purpose: Backend runtime orchestration and mode-specific execution.
- Contains: Runtime profile selection, policy inference, prompt assembly, quick mode flow, deep-research job flow, and schema definitions.
- Key files: `backend/agent/runtime.py`, `backend/agent/runtime_execution.py`, `backend/agent/quick_runtime.py`, `backend/agent/deep_research_runtime.py`, `backend/agent/prompts.py`, `backend/agent/schemas/__init__.py`

**`backend/api/`:**
- Purpose: HTTP-facing layer for the backend agent run endpoint.
- Contains: FastAPI router, service function, Pydantic request/response models, and HTTP error mapping.
- Key files: `backend/api/routes/agent_run.py`, `backend/api/services/agent_run.py`, `backend/api/schemas/agent_run.py`, `backend/api/errors.py`

**`backend/app/tools/`:**
- Purpose: Runtime tool entrypoints and supporting tool utilities.
- Contains: `web_search`, `web_crawl`, batch crawl helpers, tool error helpers, and feature-local Pydantic schemas.
- Key files: `backend/app/tools/web_search.py`, `backend/app/tools/web_crawl.py`, `backend/app/tools/web_crawl_batch.py`, `backend/app/tools/_tool_utils.py`, `backend/app/tools/schemas/web_search.py`, `backend/app/tools/schemas/web_crawl.py`

**`backend/app/crawler/`:**
- Purpose: Lower-level page retrieval, escalation, and extraction pipeline for the backend.
- Contains: HTTP and browser workers, fetch classification/strategy, extraction, content normalization, error mapping, and session-profile logic.
- Key files: `backend/app/crawler/fetch_orchestrator.py`, `backend/app/crawler/http_worker.py`, `backend/app/crawler/browser_worker.py`, `backend/app/crawler/extractor.py`, `backend/app/crawler/fetch_strategy.py`, `backend/app/crawler/schemas/`

**`backend/app/providers/`:**
- Purpose: External service clients used by backend tools.
- Contains: Serper client implementation.
- Key files: `backend/app/providers/serper_client.py`

**`src/`:**
- Purpose: TypeScript source tree for the local retrieval SDK, Express server, browser client, and tests.
- Contains: Shared core helpers, SDK entrypoints, scraper/provider infrastructure, frontend HTTP routes, browser client code, and Vitest test suites.
- Key files: `src/frontend/server.ts`, `src/sdk/search.ts`, `src/sdk/fetch.ts`, `src/scraper/orchestrator.ts`, `src/providers/serper/client.ts`

**`src/core/`:**
- Purpose: Shared TypeScript primitives that support multiple features.
- Contains: Cache, error mapping, networking guards, retrieval policy helpers, retry logic, and telemetry.
- Key files: `src/core/cache/fetch-cache.ts`, `src/core/network/resolve-and-classify.ts`, `src/core/network/redirect-guard.ts`, `src/core/policy/retrieval-controls.ts`, `src/core/telemetry/observability-logger.ts`

**`src/frontend/`:**
- Purpose: TypeScript Express server plus browser-side run UI.
- Contains: Express app boot file, API routes, browser client modules, frontend contracts, and run history storage.
- Key files: `src/frontend/server.ts`, `src/frontend/routes/search.ts`, `src/frontend/routes/fetch.ts`, `src/frontend/routes/runs.ts`, `src/frontend/routes/run-history.ts`, `src/frontend/client/app.ts`, `src/frontend/contracts.ts`, `src/frontend/run-history/store.ts`

**`src/providers/`:**
- Purpose: Third-party API adapters for the TypeScript stack.
- Contains: Serper HTTP client, request mapper, and result filtering.
- Key files: `src/providers/serper/client.ts`, `src/providers/serper/mapper.ts`, `src/providers/serper/search-request.ts`, `src/providers/serper/search-result-filter.ts`

**`src/scraper/`:**
- Purpose: Page fetch and extraction implementation for the TypeScript stack.
- Contains: HTTP worker, orchestrator, extraction, and robots helpers.
- Key files: `src/scraper/orchestrator.ts`, `src/scraper/http-worker.ts`, `src/scraper/extract.ts`, `src/scraper/robots/client.ts`, `src/scraper/robots/evaluator.ts`

**`src/sdk/`:**
- Purpose: Public retrieval API for TypeScript consumers.
- Contains: `search()` and `fetch()` entrypoints plus request/response contracts.
- Key files: `src/sdk/index.ts`, `src/sdk/search.ts`, `src/sdk/fetch.ts`, `src/sdk/contracts/search.ts`, `src/sdk/contracts/fetch.ts`, `src/sdk/contracts/safety.ts`

**`src/tests/`:**
- Purpose: TypeScript test suite.
- Contains: Integration and unit tests for fetch/search safety, frontend API routes, state reducers, and provider mapping.
- Key files: `src/tests/search/search.integration.test.ts`, `src/tests/fetch/fetch.unit.test.ts`, `src/tests/frontend-api/runs.stream.test.ts`, `src/tests/frontend/state.test.ts`

**`public/`:**
- Purpose: Static HTML shell and inline CSS for the browser app.
- Contains: Single-page HTML entry.
- Key files: `public/index.html`

**`frontend/`:**
- Purpose: Containerization assets for the frontend service.
- Contains: Dockerfile only.
- Key files: `frontend/Dockerfile`

**`dist/`:**
- Purpose: Build output for the TypeScript package.
- Contains: Generated JavaScript and type declarations from `npm run build`.
- Key files: `dist/index.js`, `dist/index.d.ts`

## Key File Locations

**Entry Points:**
- `backend/main.py`: FastAPI application factory and `/healthz` route.
- `backend/app/main.py`: Compatibility import that re-exports the FastAPI app.
- `src/frontend/server.ts`: Express app factory and executable server entrypoint.
- `public/index.html`: Browser entry HTML for the UI.
- `src/sdk/index.ts`: TypeScript SDK export surface.

**Configuration:**
- `docker-compose.yml`: Wires the `backend` and `frontend` services together.
- `backend/app/config.py`: Reads `OPENAI_API_KEY` and `SERPER_API_KEY` into cached settings.
- `package.json`: Node scripts for build, tests, and frontend server startup.
- `backend/requirements.txt`: Python dependencies for FastAPI, LangChain, crawler, and runtime support.
- `backend/Dockerfile`: Backend container image.
- `frontend/Dockerfile`: Frontend container image.

**Core Logic:**
- `backend/agent/runtime_execution.py`: Main backend runtime switchboard and LangChain agent construction.
- `backend/agent/quick_runtime.py`: Deterministic quick retrieval mode.
- `backend/app/tools/web_search.py`: Backend search tool and LangChain tool wrapper.
- `backend/app/tools/web_crawl.py`: Backend crawl tool and LangChain tool wrapper.
- `backend/app/crawler/fetch_orchestrator.py`: Backend crawl orchestration.
- `src/sdk/search.ts`: TypeScript search primitive.
- `src/sdk/fetch.ts`: TypeScript fetch primitive.
- `src/scraper/orchestrator.ts`: TypeScript fetch orchestration.
- `src/frontend/routes/runs.ts`: Frontend run creation and SSE stream handling.
- `src/frontend/run-history/store.ts`: Frontend run history persistence.

**Testing:**
- `backend/tests/`: Python pytest suite grouped by domain (`agent`, `api`, `crawler`, `tools`, `core`).
- `src/tests/`: TypeScript Vitest suite grouped by feature (`search`, `fetch`, `frontend-api`, `frontend`, `safety`).

## Naming Conventions

**Files:**
- TypeScript source files use lowercase kebab-case such as `src/frontend/run-history/store.ts`, `src/scraper/http-worker.ts`, and `src/core/policy/retrieval-controls.ts`.
- Python source files use lowercase snake_case such as `backend/agent/runtime_execution.py`, `backend/api/services/agent_run.py`, and `backend/app/crawler/fetch_orchestrator.py`.
- Schema modules are grouped into `schemas/` directories and then split by feature area, for example `backend/app/tools/schemas/web_search.py` and `backend/app/crawler/schemas/browser_fetch.py`.

**Directories:**
- Backend directories follow feature/layer names such as `backend/api/`, `backend/agent/`, `backend/app/tools/`, and `backend/app/crawler/`.
- TypeScript directories are organized by domain, not framework type, such as `src/sdk/`, `src/providers/serper/`, `src/scraper/`, `src/frontend/routes/`, and `src/frontend/client/`.
- Tests mirror the domain they exercise rather than using one flat test folder.

## Where to Add New Code

**New Backend API Endpoint:**
- Router: `backend/api/routes/`
- Request/response models: `backend/api/schemas/`
- Service logic: `backend/api/services/`
- Runtime/domain dependencies: `backend/agent/` or `backend/app/` depending on whether the behavior is agent orchestration or lower-level retrieval/tooling.

**New Backend Agent Runtime Logic:**
- Mode dispatch or shared orchestration: `backend/agent/runtime_execution.py` or a new focused module under `backend/agent/`
- Prompt/policy helpers: `backend/agent/prompts.py` or `backend/agent/runtime_policy.py`
- Output normalization: `backend/agent/runtime_sources.py`
- Schemas: nearest `schemas/` folder, usually `backend/agent/schemas/`

**New Backend Tool or Tool Schema:**
- Tool entrypoint: `backend/app/tools/`
- Tool-specific schemas: `backend/app/tools/schemas/`
- Provider adapter: `backend/app/providers/`
- Lower-level crawl/fetch logic: `backend/app/crawler/`

**New Frontend HTTP Route:**
- Route handler: `src/frontend/routes/`
- Shared request/response contract: `src/frontend/contracts.ts` or `src/frontend/contracts/` when the contract is event-specific
- Server registration: `src/frontend/server.ts`

**New Browser UI Module:**
- DOM/bootstrap/state code: `src/frontend/client/`
- Browser-visible contract aliases/parsers: `src/frontend/client/browser-contracts.ts`
- Static shell changes: `public/index.html`

**New TypeScript Retrieval Capability:**
- Public entrypoint: `src/sdk/`
- External client integration: `src/providers/`
- Crawl/fetch/search execution: `src/scraper/`
- Shared safety/policy/network/telemetry helpers: `src/core/`

**New Tests:**
- Backend tests: mirror the feature under `backend/tests/`
- TypeScript tests: mirror the feature under `src/tests/`

## Special Directories

**`.planning/codebase/`:**
- Purpose: Generated reference docs for GSD planning/execution.
- Generated: Yes
- Committed: Yes

**`dist/`:**
- Purpose: Generated TypeScript package build output.
- Generated: Yes
- Committed: Yes

**`public/`:**
- Purpose: Checked-in static frontend shell assets.
- Generated: No
- Committed: Yes

**`backend/__pycache__/` and subdirectories:**
- Purpose: Python bytecode cache.
- Generated: Yes
- Committed: Yes in current repo state

**`.worktrees/`:**
- Purpose: Local git worktree workspace storage.
- Generated: No for git metadata, but operational rather than product code.
- Committed: No

## Practical Placement Guidance

**Backend boundary rule:**
- Put HTTP request/response translation in `backend/api/`.
- Put agent orchestration and mode logic in `backend/agent/`.
- Put reusable retrieval/tool implementation in `backend/app/`.

**Frontend boundary rule:**
- Put server-side Express route handling in `src/frontend/routes/`.
- Put browser-only state and DOM manipulation in `src/frontend/client/`.
- Put reusable retrieval logic below the UI in `src/sdk/`, `src/scraper/`, `src/providers/`, and `src/core/`.

**Contract rule:**
- Use Pydantic models inside the Python feature that owns the payload, under the nearest `schemas/` folder such as `backend/app/tools/schemas/` or `backend/app/crawler/schemas/`.
- Use Zod schemas for TypeScript HTTP/browser contracts in `src/frontend/contracts.ts` and SDK contracts in `src/sdk/contracts/`.

---

*Structure analysis: 2026-03-24*
