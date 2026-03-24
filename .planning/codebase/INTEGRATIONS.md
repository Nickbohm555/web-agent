# External Integrations

**Analysis Date:** 2026-03-24

## APIs & External Services

**Search provider:**
- Serper - web search provider for both the backend tool layer and the TypeScript SDK
  - SDK/Client: Python client in `backend/app/providers/serper_client.py`; TypeScript client in `src/providers/serper/client.ts`
  - Auth: `SERPER_API_KEY` from `backend/app/config.py`, `docker-compose.yml`, and `src/providers/serper/client.ts`
  - Endpoint: `https://google.serper.dev/search` in `backend/app/providers/serper_client.py` and `src/providers/serper/client.ts`

**LLM provider:**
- OpenAI - model provider for backend agent execution and quick-answer synthesis
  - SDK/Client: `langchain-openai` `ChatOpenAI` in `backend/agent/runtime_execution.py`; direct `openai.OpenAI` client in `backend/agent/answer_synthesis.py`
  - Auth: `OPENAI_API_KEY` from `backend/app/config.py` and `docker-compose.yml`
  - Models referenced: runtime-selected `profile.model` in `backend/agent/runtime_execution.py`; `gpt-4.1-mini` default synthesis model in `backend/agent/answer_synthesis.py`

**Web retrieval targets:**
- Arbitrary public HTTP/HTTPS origins - crawl and fetch targets for evidence gathering
  - Client: `httpx` in `backend/app/crawler/http_worker.py`; `undici` in `src/scraper/http-worker.ts`
  - Policy guards: redirect/IP/domain safety in `src/core/network/`, `src/core/policy/`, and retrieval-policy enforcement in `backend/app/tools/_tool_utils.py`

**Robots policy access:**
- Per-origin `robots.txt` - fetched during TypeScript scraping workflows
  - Client: `undici` request path in `src/scraper/robots/client.ts`
  - User-Agent: `"web-agent-bot"` default in `src/scraper/robots/client.ts`

## Data Storage

**Databases:**
- Not detected
  - Connection: Not applicable
  - Client: Not applicable

**File Storage:**
- Local filesystem only
  - Static UI assets served from `public/` via `src/frontend/server.ts`
  - No object-store client or cloud file-storage SDK detected in `backend/` or `src/`

**Caching:**
- In-process memory cache for TypeScript fetch responses
  - Implementation: `createFetchCache()` in `src/sdk/fetch.ts` backed by `src/core/cache/fetch-cache.ts`
- No Redis, Memcached, or external cache service detected

## Authentication & Identity

**Auth Provider:**
- Environment-key based service auth only
  - Implementation: backend service startup requires `OPENAI_API_KEY` and `SERPER_API_KEY` in `backend/app/config.py`; TypeScript Serper client reads `SERPER_API_KEY` in `src/providers/serper/client.ts`
- No end-user auth, session store, OAuth provider, or identity middleware detected in `backend/main.py`, `backend/api/`, or `src/frontend/server.ts`

## Monitoring & Observability

**Error Tracking:**
- None detected

**Logs:**
- Structured application logging uses `pino` on the TypeScript side in `src/core/telemetry/observability-logger.ts`, `src/providers/serper/client.ts`, `src/scraper/http-worker.ts`, and `src/scraper/robots/client.ts`
- Backend tool/runtime paths return typed error envelopes but no external log sink is configured in `backend/`
- Docker log rotation is configured with the `json-file` driver in `docker-compose.yml`

## CI/CD & Deployment

**Hosting:**
- Local container deployment pattern via `docker-compose.yml`
- Backend image from `backend/Dockerfile`
- Frontend image from `frontend/Dockerfile`

**CI Pipeline:**
- Not detected

## Environment Configuration

**Required env vars:**
- `OPENAI_API_KEY` - required backend LLM provider credential in `backend/app/config.py` and `docker-compose.yml`
- `SERPER_API_KEY` - required backend/frontend search credential in `backend/app/config.py`, `docker-compose.yml`, and `src/providers/serper/client.ts`
- `AGENT_BACKEND_ORIGIN` - frontend-to-backend HTTP bridge in `docker-compose.yml`, `src/frontend/server.ts`, and `src/frontend/routes/runs.ts`
- `PORT` - frontend listen port in `docker-compose.yml` and `src/frontend/server.ts`

**Secrets location:**
- Repo-root `.env` exists for local environment configuration
- Docker Compose injects required secrets into running services in `docker-compose.yml`

## Webhooks & Callbacks

**Incoming:**
- None detected

**Outgoing:**
- `POST /api/agent/run` from the frontend service to the backend service using `AGENT_BACKEND_ORIGIN` in `src/frontend/routes/runs.ts`
- Server-sent events from `GET /api/runs/:runId/events` to browser clients in `src/frontend/routes/runs.ts` and `src/frontend/client/api-client.ts`

## Browser & Runtime Integrations

**Browser automation seam:**
- Browser-backed crawling is an injectable seam, not a configured provider
  - Interface: `browser_fetch(..., fetch_impl=...)` in `backend/app/crawler/browser_worker.py`
  - Orchestration hook: `browser_fetcher` dependency passed through `backend/app/crawler/fetch_orchestrator.py` and `backend/app/tools/web_crawl.py`
  - Current default behavior: returns `"browser fetch implementation is not configured"` when no implementation is injected in `backend/app/crawler/browser_worker.py`
- No Playwright, Puppeteer, Selenium, or Chromium package is declared in `backend/requirements.txt` or `package.json`

**Frontend browser runtime:**
- The Express frontend serves browser modules by transpiling `.ts` source on request using the `typescript` package in `src/frontend/server.ts`
- Browser clients subscribe to run progress over `EventSource` in `src/frontend/client/api-client.ts`

## Persistence & History

**Run history:**
- In-memory run/event history only
  - Store: `createRunHistoryStore()` in `src/frontend/run-history/store.ts`
  - API exposure: `src/frontend/routes/run-history.ts`
  - Lifecycle: attached to `app.locals.runHistoryStore` in `src/frontend/server.ts`
- Data is process-local and bounded by retention limits; no durable database or queue is configured

**Background execution:**
- Deep-research runs use in-process background tracking in `src/frontend/routes/runs.ts`
- Backend deep-research queueing starts from `backend/api/services/agent_run.py` and `backend/agent/deep_research_runtime.py`
- No external worker system, broker, or job queue dependency detected

---

*Integration audit: 2026-03-24*
