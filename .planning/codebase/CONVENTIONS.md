# Coding Conventions

**Analysis Date:** 2026-03-24

## Naming Patterns

**Files:**
- Python source under `backend/` uses `snake_case` module names such as `backend/api/services/agent_run.py`, `backend/app/tools/web_search.py`, and `backend/app/crawler/fetch_orchestrator.py`.
- TypeScript source under `src/` also uses kebab-case or descriptive lowercase file names with hyphens, such as `src/frontend/routes/run-history.ts`, `src/core/reliability/execute-with-retry.ts`, and `src/providers/serper/search-result-filter.ts`.
- Tests follow the runtime naming style and append `.test.py` or `.test.ts` by area, for example `backend/tests/tools/test_web_search_tool.py` and `src/tests/frontend-api/routes.contracts.test.ts`.

**Functions:**
- Python functions use `snake_case` and prefer explicit verbs: `execute_agent_run_request` in `backend/api/services/agent_run.py`, `run_web_search` in `backend/app/tools/web_search.py`, and `map_runtime_failure` in `backend/api/errors.py`.
- TypeScript functions use `camelCase` and similarly prefer direct verb names: `createFrontendServerApp` in `src/frontend/server.ts`, `createSearchRouter` in `src/frontend/routes/search.ts`, and `resolveRunRetrievalPolicy` in `src/core/policy/retrieval-controls.ts`.
- Internal helpers are prefixed with `_` in Python when they are module-private, such as `_set_route_headers` in `backend/api/routes/agent_run.py` and `_build_crawl_error_payload` in `backend/app/tools/web_crawl.py`.

**Variables:**
- Python locals and parameters stay `snake_case`, including dependency seams such as `fetch_worker`, `session_profile_provider`, and `runtime_dependencies` in `backend/app/tools/web_crawl.py` and `backend/agent/runtime_execution.py`.
- TypeScript locals stay `camelCase`, including request-scoped state like `startedAt`, `toolCallId`, and `requestBody` in `src/frontend/routes/search.ts`.
- Constants are uppercase with underscores in both stacks, for example `RUN_ROUTE_PATH` in `backend/tests/api/test_agent_run_route.py` and `DEFAULT_PORT` in `src/frontend/server.ts`.

**Types:**
- Python Pydantic models and dataclasses use `PascalCase`, for example `AgentRunRequest` in `backend/api/schemas/agent_run.py`, `WebCrawlSuccess` in `backend/app/tools/schemas/web_crawl.py`, and `RuntimeDependencies` in `backend/agent/runtime_execution.py`.
- TypeScript interfaces, schemas, and type aliases also use `PascalCase`, such as `RunState` in `src/frontend/client/state.ts`, `RunStartRequestSchema` in `src/frontend/contracts.ts`, and `SerperClientResult` in `src/providers/serper/client.ts`.

## Code Style

**Formatting:**
- No repo-level formatter config was detected for Python or TypeScript. There is no `.prettierrc`, `eslint.config.*`, `.eslintrc*`, `ruff.toml`, or `pytest.ini` at the repository root.
- TypeScript style is enforced mainly through `tsconfig.json` strictness in `tsconfig.json`: `strict`, `exactOptionalPropertyTypes`, `noUncheckedIndexedAccess`, and `verbatimModuleSyntax`.
- TypeScript imports use explicit `.js` extensions for local modules because the repo is ESM, as shown throughout `src/frontend/server.ts` and `src/sdk/search.ts`.
- Python files commonly start with `from __future__ import annotations` and fully typed signatures, as shown in `backend/main.py`, `backend/api/routes/agent_run.py`, and `backend/app/tools/web_search.py`.

**Linting:**
- No dedicated lint tool configuration is present in the repo.
- The main static guardrails are TypeScript compilation in `package.json` via `npm run typecheck` and Pydantic/Zod validation at runtime boundaries in `backend/api/schemas/agent_run.py` and `src/frontend/contracts.ts`.

## Import Organization

**Order:**
1. Standard library imports first, for example `json`, `typing`, and `time` in `backend/api/routes/agent_run.py` and `backend/app/tools/web_search.py`.
2. Third-party imports second, such as `fastapi`, `pydantic`, `express`, `undici`, and `zod`.
3. Project-local imports last, typically absolute in Python (`backend.api.schemas`) and relative in TypeScript (`../core/telemetry/call-meta.js`).

**Path Aliases:**
- No TypeScript path aliases are configured in `tsconfig.json`.
- Python imports use absolute package paths rooted at `backend`, for example `from backend.api.services.agent_run import execute_agent_run_request` in `backend/api/routes/agent_run.py`.

## Error Handling

**Patterns:**
- Validate request and response contracts at the edge, then work with typed models internally. Examples: `AgentRunRequest` in `backend/api/schemas/agent_run.py`, `WebSearchInput` and `WebSearchResponse` in `backend/app/tools/schemas/web_search.py`, and `RunStartRequestSchema` in `src/frontend/contracts.ts`.
- Map failures into explicit typed envelopes instead of returning ad hoc dictionaries. Python examples: `AgentRunErrorResponse` in `backend/api/errors.py`, `WebSearchError` in `backend/app/tools/schemas/web_search.py`, and `WebCrawlError` in `backend/app/tools/schemas/web_crawl.py`. TypeScript examples: `createErrorEnvelope` usage in `src/frontend/routes/search.ts` and SDK `SdkError` handling in `src/providers/serper/client.ts`.
- Catch `ValidationError` separately from provider/runtime failures to preserve stable invalid-request semantics, as in `backend/app/tools/web_search.py` and `backend/app/tools/web_crawl.py`.
- Service functions and routers keep the mapping boundary explicit. `backend/api/services/agent_run.py` decides whether to return a typed success model or a `JSONResponse`; `backend/api/routes/agent_run.py` adds headers but does not run agent logic directly.

## Logging

**Framework:** `pino` in TypeScript, minimal explicit logging in Python

**Patterns:**
- Provider-layer logging is concentrated in `src/providers/serper/client.ts`, where `logger.info` and `logger.error` record operation name, duration, retry count, and error class.
- Frontend API observability uses event emitters instead of plain logs in `src/core/telemetry/observability-logger.ts` and route handlers like `src/frontend/routes/search.ts`.
- Python code currently emphasizes typed error payloads over direct logging. Backend modules such as `backend/api/services/agent_run.py` and `backend/app/tools/web_search.py` generally return typed failures without writing logs.

## Comments

**When to Comment:**
- Inline comments are sparse. The codebase prefers clear function names and typed schemas over explanatory comments.
- Concise docstrings are common in backend tool modules and helper functions when the runtime shape is stable, especially under `backend/app/tools/`. Examples include `create_serper_client`, `run_web_search`, `_build_search_error_payload`, `create_http_fetch_worker`, and `run_web_crawl`.

**JSDoc/TSDoc:**
- TypeScript files rarely use JSDoc/TSDoc. Runtime behavior is usually conveyed through Zod schema names, typed signatures, and descriptive function names in `src/frontend/contracts.ts` and `src/sdk/contracts/search.ts`.
- Python docstrings in `backend/app/tools/web_search.py`, `backend/app/tools/web_crawl.py`, and `backend/app/tools/_tool_utils.py` often include one example input and one example output.

## Function Design

**Size:** Functions are kept fairly focused, but some state reducers and contracts files are intentionally large because they centralize one concern. Examples: `reduceRunState` in `src/frontend/client/state.ts` and the schema-heavy `src/frontend/contracts.ts`.

**Parameters:** Dependency seams are passed explicitly for tests rather than hidden behind generic runners. Examples:
- `build_web_search_tool(..., search_runner=...)` in `backend/app/tools/web_search.py`
- `run_web_crawl(..., fetch_worker=..., session_profile_provider=..., browser_fetcher=...)` in `backend/app/tools/web_crawl.py`
- `callSerperSearch(..., clientOptions={ requestFn, dispatcher, timeoutMs })` in `src/providers/serper/client.ts`
- `runFetchOrchestrator(..., { evaluateRobotsComplianceFn, runHttpWorkerFn })` in `src/tests/fetch/fetch.unit.test.ts`

**Return Values:** Prefer typed success/error models over raw unstructured payloads.
- Python returns Pydantic unions such as `WebSearchToolResult` and `WebCrawlToolResult` from `backend/app/tools/schemas/web_search.py` and `backend/app/tools/schemas/web_crawl.py`.
- TypeScript routes parse and return explicit Zod envelopes from `src/frontend/contracts.ts`.

## Module Design

**Exports:** Modules generally expose a small explicit surface.
- Python re-exports selected runtime functions from `backend/agent/runtime.py` through `__all__`.
- TypeScript exports named functions and types directly from focused files like `src/sdk/search.ts` and `src/frontend/routes/search.ts`.

**Barrel Files:** Barrel usage is limited and purposeful.
- Python uses package `__init__.py` files such as `backend/api/schemas/__init__.py` and `backend/agent/schemas/__init__.py` to collect related models.
- TypeScript largely imports from concrete files rather than barrel files; the closest shared edge is `src/sdk/index.ts`.

## Architectural Conventions Present In Code

- Keep HTTP route handlers thin and delegate behavior to services or SDK calls. Example split: `backend/api/routes/agent_run.py` → `backend/api/services/agent_run.py`; `src/frontend/routes/search.ts` → `src/sdk/search.ts`.
- Keep validation schemas near the feature that owns them. Current active examples include `backend/api/schemas/agent_run.py`, `backend/agent/schemas/quick_answer.py`, and `backend/app/tools/schemas/web_crawl.py`.
- Use explicit request/response contracts at boundaries, even when transport names differ. `backend/api/schemas/agent_run.py` accepts both `retrievalPolicy` and `retrieval_policy`; `src/frontend/contracts.ts` normalizes frontend camelCase payloads into canonical shapes.
- Preserve stable machine-readable error categories across layers. Examples include `_RUNTIME_ERROR_MAP` in `backend/api/errors.py`, `ToolErrorEnvelope` usage in `backend/app/tools/_tool_utils.py`, and `resolveStatusCode` in `src/frontend/routes/search.ts`.
- Prefer direct execution paths over generic framework indirection. The pattern is visible in `backend/api/services/agent_run.py`, `backend/app/tools/web_search.py`, `backend/app/tools/web_crawl.py`, and `src/providers/serper/client.ts`.

## Current Deviations And Inconsistencies

- Backend schema placement is mixed. Active feature-local schemas exist under `backend/api/schemas/`, `backend/agent/schemas/`, `backend/app/tools/schemas/`, and `backend/app/crawler/schemas/`, but older top-level modules still exist under `backend/app/schemas/` and `backend/app/contracts/`.
- Strict validation is stronger at API and tool boundaries than inside every internal helper. For example, `src/frontend/contracts.ts` and `backend/api/schemas/agent_run.py` are heavily validated, while some internal TypeScript helpers rely on trusted typed callers.
- Logging conventions are not uniform across stacks: TypeScript provider/frontend paths emit structured logs or events, while Python backend modules are mostly silent and communicate via typed payloads.

---

*Convention analysis: 2026-03-24*
