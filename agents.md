1. refer to me as Nicholas before all messages.
2. Sound like you are my employee sofware engineer.
3. If you make changes to code or see code untracked that can be commited, you MUST commit atomically and push the code.

## App Build + Debug Instructions (Operational)

Core retrieval tests require `SERPER_API_KEY` in the current environment.
If you need to test something requiring an LLM key, use `OPENAI_API_KEY` or `SERPER_API_KEY` from `keys.txt` only as a local reference, then export it into the environment before running tests.

## Runtime Stack (Current Plan)

1. Local orchestration: Docker Compose from repository root (`docker compose ...`).
2. Frontend/API server: Node.js `24` LTS (allow `22` fallback) + TypeScript (`src/frontend/**`).
3. Backend agent service: Python + FastAPI in `backend/**` (phased buildout).
4. Product tools: normalized `search(...)` and `fetch(...)` behavior with provider payloads kept internal.
5. Scraping policy: HTTP-first retrieval with selective fallback only when explicitly needed.

## Source Layout (Required)

- `src/frontend/` (TypeScript routes/server and run orchestration surface)
- `src/core/` (telemetry, retry, policy, and shared runtime utilities)
- `src/tests/` (frontend/server and integration coverage)
- `backend/app/` (Python FastAPI app, contracts, providers, tools)
- `backend/tests/` (Python backend unit/integration tests)
- `.planning/phases/` (phase research + executable task plans)

## First-Time Setup (If Missing Pieces)

Run from repository root.

1. Install Node dependencies:
   - `npm install`
2. Create Python virtual environment (for backend work):
   - `python3 -m venv .venv`
   - `source .venv/bin/activate`
3. Install backend dependencies when `backend/requirements.txt` exists:
   - `pip install -r backend/requirements.txt`
4. Ensure required env vars are exported:
   - `export OPENAI_API_KEY=...`
   - `export SERPER_API_KEY=...`
5. Validate compose wiring:
   - `docker compose config`

## Local Run Paths

Use one of these standard local workflows:

1. Compose-first (canonical once Section 1 is complete):
   - `docker compose up --build`
2. Frontend-only iterative dev (current):
   - `npm run dev:frontend`
3. Backend-only iterative dev (when backend scaffold exists):
   - `uvicorn backend.app.main:app --reload --port 8000`

## Build + Test Workflow (Every Iteration)

Run in this order; fix failures before proceeding.

1. Install/refresh JS deps: `npm install`
2. Typecheck TS: `npm run typecheck`
3. Run TS tests: `npm run test`
4. Build TS artifacts: `npm run build`
5. Run Python tests for touched backend paths (when backend exists):
   - `pytest backend/tests -q`

## Debug Workflow (Fast Path)

1. Reproduce with one command (`npm run test`, targeted Vitest file, or targeted `pytest` file).
2. Isolate the failing path:
   - Search path: `search(...)`
   - Fetch/crawl path: `fetch(...)` / `web_crawl(...)`
   - Agent run path: runtime loop or `/api/agent/run`
3. Add temporary structured logs near the failure boundary.
4. Re-run only failing tests until stable.
5. Remove/trim temporary noisy logs.
6. Re-run full validation (`typecheck`, tests, build, plus touched Python tests).

## Observability + Safety Requirements

- Use structured logs with stable correlation fields (`run_id`, `event_seq`) when implementing run telemetry.
- Never log secrets or full raw page bodies by default.
- Read keys from env vars only (`SERPER_API_KEY`, `OPENAI_API_KEY`).
- Do not read secrets directly from `keys.txt` in code paths; it is operator reference only.
- Never hardcode or commit secrets.
- Keep retries/timeouts/concurrency bounded to avoid runaway cost.

## Agent Iteration Rules

- Keep this file operational and command-focused.
- Before finishing an iteration, confirm relevant checks for touched areas:
  1. TypeScript: `npm run typecheck`, `npm run test`, `npm run build`
  2. Python backend (if touched): `pytest ...` for changed backend scope
  3. Docker/compose changes (if touched): `docker compose config` and affected service build/test path
