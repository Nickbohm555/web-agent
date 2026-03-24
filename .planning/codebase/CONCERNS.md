# Codebase Concerns

**Analysis Date:** 2026-03-24

## Tech Debt

**Split run surfaces and duplicated contracts:**
- Issue: The repo exposes two different run entrypoints with overlapping but different contracts and runtime expectations: FastAPI `POST /api/agent/run` and Express `POST /api/runs` plus SSE/history routes.
- Files: `backend/api/routes/agent_run.py`, `backend/api/services/agent_run.py`, `backend/api/schemas/agent_run.py`, `src/frontend/routes/runs.ts`, `src/frontend/contracts.ts`, `src/frontend/client/api-client.ts`
- Impact: Any change to the unified evidence contract has to be propagated across Python Pydantic models, Express route serializers, Zod contracts, browser parsers, and SSE event mappers. Drift is likely.
- Fix approach: Pick one canonical run API surface and make the other a thin adapter. Generate or centrally define the shared run/evidence schema instead of hand-maintaining both sides.

**Runtime source extraction depends on repr parsing:**
- Issue: Runtime source recovery falls back to regex parsing and `ast.literal_eval` over repr-like tool message content when typed payload extraction fails.
- Files: `backend/agent/runtime_sources.py`, `backend/tests/agent/test_runtime.py`
- Impact: Small message-format changes in LangChain/tool serialization can silently drop sources or citations, which directly threatens the current extraction pipeline and unified evidence contract work.
- Fix approach: Remove repr decoding as a primary interoperability path. Preserve typed tool payloads end-to-end and fail loudly when contracts break.

**Schema and compatibility-layer sprawl:**
- Issue: The repo contains multiple schema locations for similar concepts, including active feature-local schemas plus older compatibility folders that are not imported by current runtime code.
- Files: `backend/app/tools/schemas/`, `backend/app/crawler/schemas/`, `backend/api/schemas/`, `backend/app/schemas/`, `backend/app/contracts/`
- Impact: Contributors can place new models in the wrong layer, update stale aliases by mistake, or miss the real runtime schema used by tools and crawler code.
- Fix approach: Keep only active feature-level schemas, remove or clearly mark compatibility re-export folders, and document the canonical import path per domain.

**Oversized orchestration files:**
- Issue: Several files already concentrate multiple responsibilities despite the repo guidance favoring small, task-focused modules.
- Files: `src/frontend/routes/runs.ts`, `src/frontend/client/app.ts`, `src/frontend/client/state.ts`, `src/frontend/client/browser-contracts.ts`, `backend/agent/runtime_sources.py`, `backend/agent/runtime_execution.py`
- Impact: Implementation work in the current phase will keep landing in large coordination files, which raises regression risk and review cost.
- Fix approach: Continue carving out event mapping, background-run storage, backend bridge logic, source hydration, and runtime-mode execution into smaller modules with explicit seams.

**Duplicated fetch/crawl pipelines in two languages:**
- Issue: The repo maintains conceptually similar fetch/extraction stacks in TypeScript and Python, each with its own schemas, fallback reasons, and orchestrator logic.
- Files: `src/scraper/orchestrator.ts`, `src/scraper/http-worker.ts`, `src/sdk/contracts/fetch.ts`, `backend/app/crawler/fetch_orchestrator.py`, `backend/app/crawler/http_worker.py`, `backend/app/tools/schemas/web_crawl.py`
- Impact: Extraction behavior, fallback states, and evidence semantics can diverge across runtimes, which makes a "unified evidence contract" harder to land and verify.
- Fix approach: Treat one pipeline as the reference implementation and align the other to the same state names, metadata fields, and failure semantics.

## Known Bugs

**Deep research can be queued without any worker actually running it:**
- Symptoms: `POST /api/agent/run` can return a queued deep-research response, but no built-in scheduler or worker consumes the queued job in the default API path.
- Files: `backend/api/services/agent_run.py`, `backend/agent/deep_research_runtime.py`, `backend/agent/deep_research_store.py`, `backend/tests/api/test_agent_run_service.py`
- Trigger: Submit a request with `mode="deep_research"` through the FastAPI route without injecting `schedule_job`.
- Workaround: Inject a scheduler explicitly in tests or call `run_deep_research_job()` manually against the in-memory store.

**Run history and background-run state disappear on process restart:**
- Symptoms: Started runs, SSE replay buffers, and run history vanish when the Express process restarts.
- Files: `src/frontend/server.ts`, `src/frontend/routes/runs.ts`, `src/frontend/run-history/store.ts`
- Trigger: Restart the frontend server after creating a run or while a background run is active.
- Workaround: None beyond keeping the process alive; state is in memory only.

**Challenge detection metadata is effectively hard-coded off in success paths:**
- Symptoms: Browser-escalated crawl success records report `challenge_detected=False` even when the fetch escalated because of blocking/challenge-like conditions.
- Files: `backend/app/crawler/fetch_orchestrator.py`, `backend/app/crawler/fetch_strategy.py`, `backend/app/tools/schemas/web_crawl.py`
- Trigger: Any success path through `_run_browser_path()` after escalation from HTTP failure/classification.
- Workaround: Infer blocking from `block_reason` and `strategy_used` instead of trusting `challenge_detected`.

## Security Considerations

**Frontend server transpiles source files on demand:**
- Risk: The Express app reads `.ts` sources from `src/` and transpiles them per request. This is convenient for local development but increases attack surface and can expose source unexpectedly if reused outside a trusted local environment.
- Files: `src/frontend/server.ts`
- Current mitigation: Path normalization prevents directory traversal outside `src/frontend` and `src`.
- Recommendations: Restrict this path to development only, or replace it with a build step that serves static compiled assets.

**Operational data is stored in unauthenticated in-memory endpoints:**
- Risk: Run prompts, tool inputs/outputs, final answers, and source snippets are stored in memory and served through local HTTP routes with no authentication or tenancy boundary.
- Files: `src/frontend/routes/runs.ts`, `src/frontend/routes/run-history.ts`, `src/frontend/run-history/store.ts`, `backend/api/routes/agent_run.py`
- Current mitigation: None beyond local-process assumptions.
- Recommendations: Treat the current surfaces as local-dev only, or add auth/network restrictions before exposing them beyond localhost.

## Performance Bottlenecks

**Per-request TypeScript transpilation in the frontend server:**
- Problem: Browser module requests trigger filesystem reads and `ts.transpileModule()` on every request.
- Files: `src/frontend/server.ts`
- Cause: The app serves source modules directly instead of prebuilt assets.
- Improvement path: Build once and serve static JS, or cache transpiled output aggressively in dev.

**Search client drops connection reuse by creating ad hoc HTTP clients:**
- Problem: The default Serper client opens a fresh `httpx.Client()` for each request when no client is injected.
- Files: `backend/app/providers/serper_client.py`
- Cause: `_post()` creates a short-lived client inside each call.
- Improvement path: Reuse a shared client via application lifespan or inject a long-lived client into `SerperClient`.

**Run-history ingestion repeatedly scans and sorts bounded arrays:**
- Problem: The run-history store does linear duplicate checks and repeated sorting/eviction on ingest.
- Files: `src/frontend/run-history/store.ts`
- Cause: Event ordering and retention are maintained with array scans and resorting instead of indexed structures.
- Improvement path: Keep a per-run event-seq index and avoid re-sorting after append-only validated writes.

## Fragile Areas

**Evidence and citation hydration path:**
- Files: `backend/agent/runtime_sources.py`, `backend/agent/schemas/__init__.py`, `backend/api/schemas/agent_run.py`
- Why fragile: Source IDs, normalized URLs, citations, direct payloads, and repr-decoded fallback payloads all converge here. A small serialization change can break evidence integrity without breaking the outer run call.
- Safe modification: Change typed tool payloads and citation shape together, then run the runtime, API, and evidence-related tests as one batch.
- Test coverage: `backend/tests/agent/test_runtime.py` covers many cases, but the dependency on repr fallback is itself a fragility signal.

**Express run orchestration and SSE replay path:**
- Files: `src/frontend/routes/runs.ts`, `src/frontend/run-history/store.ts`, `src/frontend/contracts.ts`
- Why fragile: One route file owns request validation, background-run scheduling, SSE streaming, event-to-history expansion, retention, and backend bridging.
- Safe modification: Extract one concern at a time, especially event mapping and background-run storage, and keep the stream/history contract tests green.
- Test coverage: `src/tests/frontend-api/runs.stream.test.ts`, `src/tests/frontend-api/run-history.integration.test.ts`, and `src/tests/frontend-api/observability-correlation.test.ts` cover the current shape but the file remains high-churn.

**Crawler escalation semantics:**
- Files: `backend/app/crawler/fetch_orchestrator.py`, `backend/app/crawler/fetch_classification.py`, `backend/app/crawler/fetch_strategy.py`, `backend/app/crawler/error_mapping.py`
- Why fragile: HTTP failures, low-content extraction, browser-only profiles, and browser escalation all map into one success/error contract with several derived flags.
- Safe modification: Adjust state names, escalation rules, and metadata flags together; avoid changing only one layer.
- Test coverage: `backend/tests/crawler/test_fetch_orchestrator.py`, `backend/tests/crawler/test_http_worker.py`, `backend/tests/crawler/test_extractor.py`

## Scaling Limits

**Frontend background runs are intentionally capped and single-process:**
- Current capacity: `MAX_ACTIVE_BACKGROUND_RUNS = 3`, `MAX_BACKGROUND_RUNS = 25`, `MAX_BACKGROUND_EVENTS_PER_RUN = 100`
- Limit: Additional deep-research runs are rate-limited, completed run buffers are evicted, and active state cannot be shared across processes.
- Scaling path: Move run coordination and event persistence out of process memory into a durable queue/store before increasing concurrency.
- Files: `src/frontend/routes/runs.ts`

**Run history is bounded and lossy by design:**
- Current capacity: Defaults are `25` runs, `100` events per run, and `32_768` bytes per event payload.
- Limit: Older runs are evicted, old events are dropped, and payloads/final answers are truncated once limits are exceeded.
- Scaling path: Persist canonical events durably and use bounded caches only for UI convenience.
- Files: `src/frontend/run-history/store.ts`

**Deep research state is single-process and in-memory only:**
- Current capacity: One Python process with an in-memory dictionary store.
- Limit: Jobs are lost on restart and cannot be shared with another worker or API replica.
- Scaling path: Replace `InMemoryDeepResearchStore` with durable storage plus an explicit worker/scheduler.
- Files: `backend/agent/deep_research_store.py`, `backend/agent/deep_research_runtime.py`

## Dependencies at Risk

**Serper as the only search provider:**
- Risk: Search behavior, freshness mapping, and availability all hinge on one provider integration with no alternate backend.
- Impact: Provider outages or API behavior changes directly degrade retrieval quality and can block evidence gathering.
- Migration plan: Add a provider abstraction with at least one fallback implementation before widening production usage.
- Files: `backend/app/providers/serper_client.py`, `backend/app/tools/web_search.py`, `src/providers/serper/client.ts`, `src/providers/serper/mapper.ts`

**Tool-message shape dependence through LangChain-style runtime serialization:**
- Risk: The runtime still relies on tool/message structures that may vary by framework version or executor path.
- Impact: Source extraction and citation hydration can degrade even when tool execution still "works."
- Migration plan: Normalize tool output into explicit internal envelopes before runtime parsing instead of inspecting framework message objects.
- Files: `backend/agent/runtime_execution.py`, `backend/agent/runtime_sources.py`, `backend/app/tools/web_search.py`, `backend/app/tools/web_crawl.py`

## Missing Critical Features

**No durable end-to-end deep-research execution path:**
- Problem: The code can represent and verify deep-research jobs, but the default API path does not ship with a durable scheduler/worker or a retrieval surface to observe job progress from the Python side.
- Blocks: Reliable background execution, restart recovery, and production-style long-running research.
- Files: `backend/api/services/agent_run.py`, `backend/agent/deep_research_runtime.py`, `backend/agent/deep_research_store.py`

**No single source of truth for the evidence contract across Python and TypeScript:**
- Problem: The same concepts exist in Python Pydantic models, Express/Zod contracts, browser parsers, and test fixtures without shared generation.
- Blocks: Fast, low-risk iteration on the current extraction pipeline + unified evidence contract phase.
- Files: `backend/agent/schemas/__init__.py`, `backend/api/schemas/agent_run.py`, `backend/app/tools/schemas/web_crawl.py`, `src/frontend/contracts.ts`, `src/frontend/client/browser-contracts.ts`

## Test Coverage Gaps

**No real end-to-end bridge test across Express and FastAPI surfaces:**
- What's not tested: A live `/api/runs` flow proxied into the real FastAPI `/api/agent/run` surface with the same evidence payload shape.
- Files: `src/frontend/routes/runs.ts`, `backend/api/routes/agent_run.py`
- Risk: The two API seams can drift while each side still passes its own tests.
- Priority: High

**No default-path test proving deep-research jobs actually execute after queueing:**
- What's not tested: The production-like case where `POST /api/agent/run` queues a deep-research job and a real scheduler/worker picks it up.
- Files: `backend/api/services/agent_run.py`, `backend/agent/deep_research_runtime.py`
- Risk: Background research can appear supported while remaining effectively inert.
- Priority: High

**Limited contract protection around duplicated extraction semantics across TS and Python:**
- What's not tested: Cross-runtime parity for fallback reasons, evidence metadata flags, and excerpt behavior between the TypeScript fetch stack and the Python crawler stack.
- Files: `src/scraper/orchestrator.ts`, `backend/app/crawler/fetch_orchestrator.py`
- Risk: The current extraction/evidence work can ship with divergent semantics depending on which runtime path is exercised.
- Priority: Medium

---

*Concerns audit: 2026-03-24*
