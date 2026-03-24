# Technology Stack

**Analysis Date:** 2026-03-24

## Languages

**Primary:**
- TypeScript 5.9.x - SDK, frontend server, frontend API routes, client code, and tests in `package.json`, `tsconfig.json`, `src/sdk/`, `src/frontend/`, `src/core/`, `src/scraper/`, and `src/tests/`
- Python 3.12 - agent runtime, API layer, crawler/tooling, and backend tests in `backend/Dockerfile`, `backend/main.py`, `backend/api/`, `backend/agent/`, `backend/app/`, and `backend/tests/`

**Secondary:**
- HTML/CSS/JS assets - browser UI entrypoint and static assets served from `public/index.html` and `public/`
- Markdown - repo and planning docs in `README.md` and `.planning/`

## Runtime

**Environment:**
- Node.js 24 - container runtime for the TypeScript frontend/service layer in `frontend/Dockerfile`
- Python 3.12 - container runtime for the FastAPI backend in `backend/Dockerfile`

**Package Manager:**
- npm - root TypeScript package manager defined by `package.json`
- Lockfile: present in `package-lock.json`
- pip - backend Python dependencies installed from `backend/requirements.txt`
- Lockfile: missing for Python dependencies

## Frameworks

**Core:**
- Express 5.2.1 - frontend HTTP server and local API surface in `package.json`, `src/frontend/server.ts`, and `src/frontend/routes/*.ts`
- FastAPI 0.115.12 - backend HTTP API and health endpoint in `backend/requirements.txt`, `backend/main.py`, and `backend/api/routes/agent_run.py`
- LangChain 0.3.27 - backend tool registration and agent construction in `backend/requirements.txt`, `backend/app/tools/web_search.py`, `backend/app/tools/web_crawl.py`, and `backend/agent/runtime_execution.py`
- LangGraph 0.6.11 - fallback agent factory for react-agent execution in `backend/requirements.txt` and `backend/agent/runtime_execution.py`

**Testing:**
- Vitest 4.1.0 - TypeScript unit/integration tests in `package.json` and `src/tests/`
- pytest - Python test runner pattern inferred from `backend/tests/` imports and test naming in `backend/tests/**/*.py`

**Build/Dev:**
- tsdown 0.21.3 - ESM SDK bundling and declaration output in `package.json`
- tsx 4.21.0 - direct TypeScript execution for SDK and frontend dev entrypoints in `package.json`
- TypeScript compiler - typechecking/transpile settings in `tsconfig.json`
- Uvicorn 0.34.0 - backend ASGI server in `backend/requirements.txt` and `backend/Dockerfile`
- Docker Compose - local multi-service orchestration in `docker-compose.yml`

## Key Dependencies

**Critical:**
- `langchain-openai` 0.3.35 - OpenAI-backed chat model integration for backend agent execution in `backend/requirements.txt` and `backend/agent/runtime_execution.py`
- `httpx` 0.28.1 - backend HTTP transport for Serper and crawl requests in `backend/requirements.txt`, `backend/app/providers/serper_client.py`, and `backend/app/crawler/http_worker.py`
- `undici` 7.24.3 - TypeScript HTTP transport for search, fetch, and robots access in `package.json`, `src/providers/serper/client.ts`, and `src/scraper/robots/client.ts`
- `trafilatura` 2.0.0 - backend HTML-to-text extraction in `backend/requirements.txt` and `backend/app/crawler/extractor.py`
- `zod` 4.3.6 - TypeScript request/response validation and browser contract parsing in `package.json`, `src/frontend/contracts.ts`, and `src/sdk/contracts/*.ts`
- `pydantic-settings` 2.8.1 - backend env-backed settings in `backend/requirements.txt` and `backend/app/config.py`

**Infrastructure:**
- `pino` 10.3.1 - TypeScript structured logging and observability events in `package.json`, `src/core/telemetry/observability-logger.ts`, `src/providers/serper/client.ts`, and `src/scraper/http-worker.ts`
- `@mozilla/readability` 0.6.0 - TypeScript content extraction support in `package.json` and `src/scraper/extract.ts`
- `cheerio` 1.2.0 - HTML parsing in the TypeScript scraper path in `package.json` and `src/scraper/extract.ts`
- `robots-parser` 3.0.1 - robots.txt policy parsing in the TypeScript fetch path in `package.json` and `src/scraper/robots/evaluator.ts`
- `turndown` 7.2.2 - markdown conversion in the TypeScript scraper path in `package.json` and `src/scraper/extract.ts`
- `dotenv` 17.3.1 - local env loading support on the TypeScript side in `package.json`

## Configuration

**Environment:**
- Required backend secrets are `OPENAI_API_KEY` and `SERPER_API_KEY` via `backend/app/config.py` and enforced in `docker-compose.yml`
- Frontend runtime wiring uses `AGENT_BACKEND_ORIGIN` and `PORT` in `docker-compose.yml` and `src/frontend/server.ts`
- Logging level is controlled by optional `LOG_LEVEL` reads in `src/core/telemetry/observability-logger.ts`, `src/providers/serper/client.ts`, `src/scraper/http-worker.ts`, and `src/scraper/robots/client.ts`
- `.env` file is present at repo root; treat it as environment configuration only and do not read its contents

**Build:**
- Root TypeScript compiler settings live in `tsconfig.json`
- Frontend container build is defined in `frontend/Dockerfile`
- Backend container build is defined in `backend/Dockerfile`
- Service composition, healthchecks, and required env propagation live in `docker-compose.yml`
- SDK package entrypoints and scripts live in `package.json`

## Platform Requirements

**Development:**
- Docker and Docker Compose for the default two-service local stack in `docker-compose.yml`
- Node.js/npm to run `npm run typecheck`, `npm run test`, `npm run build`, and `npm run dev:frontend` from `package.json`
- Python with pip if running the backend outside containers using `backend/requirements.txt`

**Production:**
- Containerized deployment shape with a FastAPI backend on port `8000` from `backend/Dockerfile` and an Express frontend on port `3000` from `frontend/Dockerfile`
- Frontend expects network reachability to the backend origin configured by `AGENT_BACKEND_ORIGIN` in `src/frontend/server.ts` and `docker-compose.yml`

---

*Stack analysis: 2026-03-24*
