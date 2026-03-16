## App Build + Debug Instructions (Operational)

Core retrieval tests require `SERPER_API_KEY` in the current environment.
If you need to test something requiring an LLM key, use `OPENAI_API_KEY` from `keys.txt` only as a local reference, then export it into the environment before running tests.

1. Stack: Node.js `24` LTS (allow `22` fallback) + TypeScript `^5.7` + SDK-first architecture.
2. Product surface: TypeScript SDK methods `search(...)` and `fetch(...)`.
3. Core internals: Serper adapter + in-house scraper with HTTP-first and selective browser fallback.
4. Do not use browser-first scraping by default.
5. Keep provider payloads internal; return only normalized SDK contracts.

## Source Layout (Required)

- `src/sdk/` (public API + contracts)
- `src/core/` (retry, policy, cache, telemetry, concurrency)
- `src/providers/serper/` (Serper integration)
- `src/scraper/` (orchestrator, workers, extraction, robots)
- `src/tests/` (unit + integration)

## First-Time Project Setup (If Repo Is Not Scaffolded Yet)

Run these commands from repo root:

1. `npm init -y`
2. `npm install undici cheerio p-retry p-queue zod robots-parser tldts @mozilla/readability turndown pino`
3. `npm install -D typescript tsdown vitest tsx @types/node`
4. `npx tsc --init`
5. Create baseline dirs:
   - `mkdir -p src/sdk src/core src/providers/serper src/scraper src/tests`
6. Add scripts in `package.json`:
   - `"typecheck": "tsc --noEmit"`
   - `"test": "vitest run"`
   - `"test:watch": "vitest"`
   - `"build": "tsdown"`
   - `"dev": "tsx src/sdk/index.ts"`

## Build the App (Every Iteration)

Use this exact order:

1. Install/refresh deps: `npm install`
2. Typecheck: `npm run typecheck`
3. Run tests: `npm run test`
4. Build: `npm run build`

If any step fails, fix before moving forward.

## Debug Workflow (Fast Path)

When something breaks, use this sequence:

1. Reproduce with one command (`npm run test` or one failing test file).
2. Isolate to one path:
   - Search path: `search(...)`
   - Fetch path: `fetch(...)`
3. Add temporary structured logs around failure boundary.
4. Re-run only the failing test(s).
5. Remove/trim noisy temporary logs once fixed.
6. Run full `typecheck + test + build` again.

## Path-Specific Debug Checklists

Search (`search(...)`):
- Validate request/options with `zod`.
- Verify cache key normalization and cache hit/miss logic.
- Verify Serper response mapping to SDK contract.
- Verify retry/timeout bounds for `429` and `5xx`.

Fetch (`fetch(...)`):
- Validate URL normalization and domain parsing.
- Verify `robots.txt`/politeness gate executes before outbound fetch.
- Confirm HTTP-first path is attempted before fallback.
- Confirm fallback reason is explicit (network error vs low content quality).
- Verify extracted output is normalized and stable.

## Observability + Safety Requirements

- Use structured logs (`pino`) with operation, duration, retry count, and error class.
- Never log secrets or full raw page bodies by default.
- Read keys from environment variables only (`SERPER_API_KEY`, `OPENAI_API_KEY` when needed).
- Do not read secrets directly from `keys.txt` in code paths; treat it as a local operator reference only.
- Never hardcode or commit secrets.
- Keep retries and concurrency capped to prevent runaway cost.

## Agent Iteration Rules

- Keep this file operational and command-focused.
- Before finishing an iteration, confirm:
  1. `npm run typecheck` passes
  2. `npm run test` passes (or expected failures are documented)
  3. `npm run build` passes
