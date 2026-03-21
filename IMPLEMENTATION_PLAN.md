# Implementation Plan
Current Section: 22

## Section 1: Define Search Mode Contract

Task:
Add a first-class run/search mode contract that distinguishes `quick`, `agentic`, and `deep_research` execution profiles.

Context:
The current run-start shape only accepts a prompt, which prevents the system from expressing meaningful differences in latency, planning depth, and execution strategy. This contract should be the single entry point for mode selection across frontend and backend APIs. Keep the shape small at first, but leave room for future controls such as reasoning level and domain scope.

Where to Look / Add:
- `src/frontend/contracts.ts`
- `src/frontend/client/api-client.ts`
- `backend/api/contracts.py`

How to Test:
- `npm run test -- src/tests/frontend-api/runs.contracts.test.ts`
- `pytest backend/tests/api/test_agent_run_route.py -q`
Success looks like mode-bearing requests validating cleanly in both frontend and backend contracts, while unknown or malformed mode values fail with explicit schema errors. We know this section is working when a run can carry the selected mode end-to-end without falling back to prompt-only behavior.

Completion Note:
Do not end this section until it has been thoroughly tested.

## Section 2: Route Mode Execution Through Run APIs

✓ Completed: `/api/runs` now registers mode-aware runs, executes them through an executor-backed SSE flow when a run executor is configured, preserves stream/history integration, and keeps `/api/agent/run` as a thin legacy compatibility route with explicit compatibility headers.

Task:
Make `/api/runs` the primary execution surface for mode-aware runs and limit the legacy synchronous agent route to compatibility behavior.

Context:
This repo already has queue/start, SSE, and history primitives under the frontend run APIs, which fit long-running research much better than the older single-response backend route. Building mode support around `/api/runs` avoids duplicating execution contracts and keeps deep research compatible with existing live-progress UX. The synchronous `/api/agent/run` path should either be reduced to a thin shim or explicitly scoped to non-background use cases.

Where to Look / Add:
- `src/frontend/routes/runs.ts`
- `src/frontend/server.ts`
- `backend/api/routes/agent_run.py`
- `backend/api/routes/`

How to Test:
- `npm run test -- src/tests/frontend-api/runs.stream.test.ts`
- `npm run test -- src/tests/frontend-api/runs.contracts.test.ts`
Success looks like `/api/runs` accepting mode-aware run creation and continuing to drive the live stream/history path without contract regressions. We know this section is working when the primary run flow starts, streams, and completes through `/api/runs` while the legacy route stays clearly bounded or intentionally compatible.

Completion Note:
Do not end this section until it has been thoroughly tested.

## Section 3: Refactor Backend Runtime Into Profiles

✓ Completed: Backend runtime now selects explicit `quick`, `agentic`, and `deep_research` profiles with distinct model, recursion budget, timeout, execution mode, and prompt guidance, while preserving canonical tool binding and stable failure mapping through runtime tests.

Task:
Replace the fixed backend runtime configuration with a profile-driven executor that selects model, recursion budget, timeout policy, and execution mode per run profile.

Context:
The current runtime hardcodes one model and one recursion limit, which is only suitable for a single generic agent flow. A profile layer should centralize decisions about model choice, autonomy level, and budget controls so all three modes are explicit and testable. Keep canonical tool bindings intact while moving orchestration policy out of the single `run_agent_once` implementation.

Where to Look / Add:
- `backend/agent/runtime.py`
- `backend/agent/types.py`
- `backend/agent/prompts.py`
- `backend/agent/`

How to Test:
- `pytest backend/tests/agent/test_runtime.py -q`
Success looks like runtime tests proving each profile selects the intended execution policy, budgets, and failure mapping instead of reusing one hardcoded path. We know this section is working when changing the selected profile materially changes runtime behavior in test fixtures.

Completion Note:
Do not end this section until it has been thoroughly tested.

## Section 4: Implement Quick Search Execution

✓ Completed: `quick` now bypasses the autonomous agent loop, performs exactly one normalized `web_search` pass, synthesizes a sourced answer from validated search results, and maps malformed/provider failures into stable runtime errors with backend tests covering the single-search path.

Task:
Add a constrained `quick` execution path that performs one normalized web search and synthesizes a sourced answer without autonomous follow-up loops.

Context:
This mode should approximate OpenAI’s non-reasoning web search behavior and optimize for speed rather than deep exploration. It should use the existing normalized search tool and stop after one search pass unless validation fails. Keep the answer contract compatible with later citation/source rendering work.

Where to Look / Add:
- `backend/app/tools/web_search.py`
- `backend/agent/runtime.py`
- `backend/agent/`

How to Test:
- `pytest backend/tests/agent/test_runtime.py -q`
- `pytest backend/tests/tools/test_web_search_tool.py -q`
Success looks like the `quick` profile issuing one normalized search pass and producing a usable answer without autonomous follow-up crawl loops. We know this section is working when runtime tests show a single search-driven synthesis path and tool tests still preserve stable search behavior.

Completion Note:
Do not end this section until it has been thoroughly tested.

## Section 5: Implement Agentic Search Execution

✓ Completed: `agentic` now builds profile-bound `web_search` and `web_crawl` wrappers with explicit search-result, crawl-content, and tool-step budgets, feeds those limits into runtime config and prompt guidance, and preserves stable failure mapping through runtime and tool coverage.

Task:
Add a configurable `agentic` execution path that uses bounded reasoning over `web_search` and `web_crawl`.

Context:
This is the closest fit to the current agent loop, but it needs profile-aware limits and cleaner control over planning depth. The implementation should preserve your normalized tool interfaces while allowing model choice and recursion budgets to vary by profile. Keep failure mapping explicit so tool, provider, and loop-limit errors remain stable at the API boundary.

Where to Look / Add:
- `backend/agent/runtime.py`
- `backend/agent/prompts.py`
- `backend/app/tools/web_search.py`
- `backend/app/tools/web_crawl.py`

How to Test:
- `pytest backend/tests/agent/test_runtime.py -q`
- `pytest backend/tests/tools/test_web_search_tool.py -q`
- `pytest backend/tests/tools/test_web_crawl_tool.py -q`
Success looks like the `agentic` profile performing bounded multi-step search and crawl behavior with explicit loop limits and stable error mapping. We know this section is working when runtime fixtures show multiple deliberate tool steps while failures still surface as the expected provider, tool, timeout, or loop-limit categories.

Completion Note:
Do not end this section until it has been thoroughly tested.

## Section 6: Implement Deep Research Background Runs

✓ Completed: `deep_research` now starts on `POST /api/runs`, executes in a buffered background registry instead of waiting for the SSE request, replays ordered progress events to late subscribers, and persists intermediate/final events into run history before stream consumption.

Task:
Add a `deep_research` execution path that runs as a long-lived background job and emits progress through the existing run stream/history system.

Context:
Deep research should not depend on one long open request because it may run for minutes and needs durable progress visibility. The clean fit in this codebase is a background executor that produces incremental run events, persists them into the history store, and completes asynchronously. Design the first version with bounded depth and retention so it remains observable and safe under failure.

Where to Look / Add:
- `src/frontend/routes/runs.ts`
- `src/frontend/run-history/store.ts`
- `backend/agent/`
- `backend/api/routes/`

How to Test:
- `npm run test -- src/tests/frontend-api/runs.stream.test.ts`
- `npm run test -- src/tests/frontend-api/run-history.integration.test.ts`
Success looks like long-running runs continuing asynchronously while emitting ordered progress into SSE and retained history snapshots. We know this section is working when a deep-research run can outlive the start request, stream multiple intermediate events, and still appear intact in run history afterward.

Completion Note:
Do not end this section until it has been thoroughly tested.

## Section 7: Expand Run Event Schema For Research Progress

✓ Completed: Canonical run events now support explicit planning, source-expansion, and synthesis milestones with validated progress metadata, the client reducer synthesizes those stages for live runs, and timeline/preview rendering shows richer research progress without regressing simpler run traces.

Task:
Extend run event contracts and UI state handling to represent richer research progress beyond generic tool-call events.

Context:
Deep research benefits from clearer stage visibility such as planning, source expansion, synthesis, and completion milestones. The current SSE schema is intentionally small, so changes here should preserve validation rigor and history truncation behavior. Keep the event model coherent enough that quick and agentic modes can still use the same timeline components without branching everywhere in the UI.

Where to Look / Add:
- `src/frontend/contracts.ts`
- `src/frontend/client/state.ts`
- `src/frontend/client/app.ts`
- `src/frontend/client/timeline.ts`

How to Test:
- `npm run test -- src/tests/frontend-api/run-events.contracts.test.ts`
- `npm run test -- src/tests/frontend/state.test.ts`
- `npm run test -- src/tests/frontend/timeline.test.ts`
Success looks like richer event variants validating through the contracts and rendering coherently in the timeline without breaking simpler runs. We know this section is working when new progress stages appear in UI state/tests and existing quick or agentic events still render correctly.

Completion Note:
Do not end this section until it has been thoroughly tested.

## Section 8: Unify Retrieval Policy Controls At Run Level

✓ Completed: Added a normalized run-level `retrievalPolicy` contract shared across frontend and backend run APIs, merged that policy into downstream search/fetch controls, and enforced the same domain-scope and freshness constraints across quick, agentic, and deep-research execution paths with expanded integration/runtime/tool coverage.

Task:
Promote retrieval policy inputs such as domain scope and freshness into a run-level control surface shared across all three modes.

Context:
Your repo already has search and fetch control utilities, but they are primarily expressed at the individual tool layer. A run-level retrieval policy keeps user intent coherent and allows each mode to respect the same constraints while implementing different orchestration strategies. Preserve current safety checks and avoid introducing mode-specific policy drift.

Where to Look / Add:
- `src/core/policy/retrieval-controls.ts`
- `src/sdk/contracts/search.ts`
- `backend/api/contracts.py`
- `backend/agent/`

How to Test:
- `npm run test -- src/tests/search-controls.integration.test.ts`
- `npm run test -- src/tests/fetch-controls.integration.test.ts`
Success looks like run-level policy inputs being applied consistently to retrieval behavior regardless of execution mode. We know this section is working when domain scope and freshness constraints show up in downstream search/fetch behavior without mode-specific drift.

Completion Note:
Completed with `npm run test -- src/tests/search-controls.integration.test.ts`, `npm run test -- src/tests/fetch-controls.integration.test.ts`, `npm run typecheck`, `npm run test`, `npm run build`, and `pytest backend/tests/api/test_agent_run_route.py backend/tests/agent/test_runtime.py backend/tests/tools/test_web_search_tool.py backend/tests/tools/test_web_crawl_tool.py -q`.

## Section 9: Add Source-Aware Answer Contracts

✓ Completed: Added a normalized `sources` contract to backend run results and API responses, propagated source references through the frontend executor and completion events, and validated the new provenance shape in backend/runtime/frontend tests.

Task:
Extend run result contracts to include normalized citations or source references alongside the final answer.

Context:
Right now the agent result shape emphasizes final text and tool-call counts, which is insufficient for a retrieval-heavy product. Source-aware contracts will make answers more trustworthy and align the UI with the behavior users expect from web-grounded search. Keep the schema normalized so all modes can return sources even if the number and depth of citations differ.

Where to Look / Add:
- `backend/agent/types.py`
- `backend/api/contracts.py`
- `src/frontend/contracts.ts`
- `src/frontend/client/app.ts`

How to Test:
- `pytest backend/tests/api/test_agent_run_route.py -q`
- `npm run test -- src/tests/frontend-api/routes.contracts.test.ts`
Success looks like completed runs returning structured provenance data instead of plain answers only, while frontend contracts continue to validate the response shape. We know this section is working when cited or sourced answers can cross the API boundary without ad hoc parsing.

Completion Note:
Completed with `pytest backend/tests/api/test_agent_run_route.py -q`, `pytest backend/tests/agent/test_runtime.py -q`, `npm run test -- src/tests/frontend-api/routes.contracts.test.ts`, `npm run typecheck`, `npm run test`, and `npm run build`.

## Section 10: Preserve Observability And Safety Bounds

✓ Completed: Added resumable run-context sequencing, hard-capped observability payload bytes, bounded deep-research background concurrency and replay buffers, trimmed retained truncation metadata, and enforced backend retry-attempt guardrails with new frontend/backend coverage.

Task:
Ensure all run modes emit stable telemetry and remain bounded on retries, payload size, concurrency, and retained history.

Context:
Longer-running research increases both cost risk and operational complexity, so observability and safety requirements need to stay first-class as execution modes expand. The repo already has telemetry context, payload truncation, and run-history retention rules that should be reused rather than bypassed. Treat this as an implementation gate, not a cleanup task after the fact.

Where to Look / Add:
- `src/core/telemetry/run-context.ts`
- `src/core/telemetry/observability-logger.ts`
- `src/frontend/run-history/store.ts`
- `backend/app/core/retry.py`

How to Test:
- `npm run test -- src/tests/frontend-api/observability-correlation.test.ts`
- `npm run test -- src/tests/frontend-api/run-history.integration.test.ts`
- `pytest backend/tests -q`
Success looks like telemetry, truncation, and retry bounds staying intact even as run complexity increases across modes. We know this section is working when event correlation remains stable, oversized payloads are handled safely, and no mode bypasses the existing guardrails.

Completion Note:
Completed with `npm run test -- src/tests/frontend-api/observability-correlation.test.ts`, `npm run test -- src/tests/frontend-api/run-history.integration.test.ts`, `pytest backend/tests -q`, `npm run typecheck`, `npm run test`, and `npm run build`.

## Section 11: Add Mode Selection To The Frontend

✓ Completed: Added an explicit frontend mode picker for quick search, agentic search, and deep research; stored the selected mode in client state; sent it through the run-start request; surfaced the current mode in run status copy; and hardened deep-research history timing coverage during full-suite validation.

Task:
Update the UI so users can explicitly choose between quick search, agentic search, and deep research before starting a run.

Context:
These modes represent materially different latency and depth tradeoffs, so they should be visible and intentional in the product surface. The UX should communicate that quick search is fast, agentic search is exploratory, and deep research may take much longer. Keep the initial UI simple and make sure the choice flows cleanly into the run-start API contract.

Where to Look / Add:
- `public/index.html`
- `src/frontend/client/app.ts`
- `src/frontend/client/state.ts`

How to Test:
- `npm run test -- src/tests/frontend/state.test.ts`
- `npm run test -- src/tests/frontend/timeline.test.ts`
Success looks like users being able to choose a mode in the UI and seeing that choice reflected in state and run behavior without ambiguity. We know this section is working when state tests capture the chosen mode and the timeline/history remain coherent after runs start from the updated interface.

Completion Note:
Completed with `npm run test -- src/tests/frontend/state.test.ts`, `npm run test -- src/tests/frontend/timeline.test.ts`, `npm run typecheck`, `npm run test`, and `npm run build`.
Do not end this section until it has been thoroughly tested.

## Section 12: Lock Down End-To-End Mode Coverage

✓ Completed: Added explicit end-to-end happy/failure mode matrices for `/api/runs`, legacy `/api/agent/run`, and runtime profile execution so `quick`, `agentic`, and `deep_research` each verify coherent start, stream, completion/history, and stable failure behavior through full frontend/backend validation.

Task:
Add an end-to-end verification matrix covering happy-path and failure-path behavior for all three execution modes.

Context:
The largest regression risk is contract drift between the legacy synchronous path, the new run-based execution path, and the different runtime profiles. This final section should confirm that each mode starts correctly, emits coherent events, preserves history, and returns stable errors under bounded failure scenarios. Use the existing iteration workflow from `AGENTS.md` to finish with full validation.

Where to Look / Add:
- `src/tests/frontend-api/`
- `backend/tests/api/`
- `backend/tests/agent/`

How to Test:
- `npm run typecheck`
- `npm run test`
- `npm run build`
- `pytest backend/tests -q`
Success looks like the entire mode matrix passing both focused and full-suite validation with no contract drift between start, stream, completion, and history surfaces. We know this section is working when all three modes have at least one happy path and one failure path covered and the full repo validation loop passes cleanly.

Completion Note:
Completed with `npm run typecheck`, `npm run test -- src/tests/frontend-api/run-history.integration.test.ts`, `pytest backend/tests/api/test_agent_run_route.py backend/tests/agent/test_runtime.py -q`, `npm run test`, `npm run build`, and `pytest backend/tests -q`.

## Section 13: Define Structured Answer Output

✓ Completed: Replaced plain-string backend/frontend final-answer contracts with a structured answer object carrying answer text plus citation spans, normalized source records with stable `source_id` values, preserved runtime compatibility by coercing legacy string answers into the new shape, and updated route/integration coverage to validate the typed response boundary.

Task:
Add a structured final-answer contract that can represent answer text, inline citations, and consulted sources instead of only a plain string.

Context:
Your current run result models only expose `final_answer`, which is too limited to support OpenAI-style citation-rich responses. The new shape should support span-based citations, source identifiers, and a normalized source list that can be shared across quick, agentic, and deep-research modes. Keep the model simple enough to land incrementally without forcing all rendering logic into one change.

Where to Look / Add:
- `backend/agent/types.py`
- `backend/api/contracts.py`
- `src/frontend/contracts.ts`

How to Test:
- `pytest backend/tests/api/test_agent_run_route.py -q`
- `npm run test -- src/tests/frontend-api/routes.contracts.test.ts`
Success looks like final responses carrying structured answer objects that validate cleanly across backend and frontend boundaries. We know this section is working when answers can include text, citations, and sources without forcing either side to treat them as untyped blobs.

Completion Note:
Completed with `./.venv/bin/pytest backend/tests/api/test_agent_run_route.py -q`, `npm run test -- src/tests/frontend-api/routes.contracts.test.ts`, `./.venv/bin/pytest backend/tests/agent/test_runtime.py -q`, `npm run typecheck`, `npm run test`, and `npm run build`.

## Section 14: Normalize Citation Spans

✓ Completed: Added explicit citation annotations with stable `source_id`, `title`, `url`, and text spans; validated citation ranges against final answer text with deterministic overlap/bounds rejection; and wired runtime extraction to preserve structured citation metadata from assembled answers.

Task:
Introduce a citation annotation model with explicit text spans, target URLs, titles, and stable source IDs.

Context:
OpenAI’s `url_citation` model relies on metadata, not text parsing, which makes rendering deterministic. Your implementation should do the same so the frontend never has to infer citations from answer prose. Validate spans carefully to prevent broken or overlapping citation ranges from leaking into stored history or rendered output.

Where to Look / Add:
- `backend/agent/types.py`
- `backend/agent/runtime.py`
- `backend/tests/agent/`

How to Test:
- `pytest backend/tests/agent/test_runtime.py -q`
Success looks like citation metadata surviving runtime assembly with valid spans, stable source IDs, and no malformed overlap cases. We know this section is working when test fixtures can assert exact span locations and reject broken annotations deterministically.

Completion Note:
Completed with `pytest backend/tests/agent/test_runtime.py -q`, `pytest backend/tests -q`, `npm run typecheck`, `npm run test`, and `npm run build`.

## Section 15: Expand Streamed Retrieval Action Events

✓ Completed: Added typed `retrieval_action` SSE events for search, page-open, and in-page lookup activity; expanded canonical run-history events with explicit retrieval-action lifecycle records; and preserved ordered stream-to-history ingestion without falling back to generic tool-call payloads.

Task:
Extend the SSE and run-history event contracts so retrieval actions are represented explicitly rather than only as generic tool lifecycle events.

Context:
Right now the frontend only sees `tool_call` status changes, which is enough for coarse tracing but not enough for rich search transparency. Add explicit action records for search calls, page opens, and in-page lookup behavior while preserving event ordering, safety metadata, and truncation semantics. Keep the event model typed so the frontend can render process detail without inspecting arbitrary payloads.

Where to Look / Add:
- `src/frontend/contracts.ts`
- `src/frontend/contracts/run-events.ts`
- `src/frontend/routes/runs.ts`

How to Test:
- `npm run test -- src/tests/frontend-api/run-events.contracts.test.ts`
- `npm run test -- src/tests/frontend-api/runs.stream.test.ts`
Success looks like streamed retrieval actions validating as typed events and appearing in order on the live run stream. We know this section is working when search/open/find style actions can be emitted and consumed without collapsing back into generic unstructured payloads.

Completion Note:
Completed with `npm run test -- src/tests/frontend-api/run-events.contracts.test.ts`, `npm run test -- src/tests/frontend-api/runs.stream.test.ts`, `npm run typecheck`, and `npm run build`.

## Section 16: Map Canonical Tools To Richer Action Records

✓ Completed: Added backend-side search/crawl action-record normalizers that preserve stable tool outputs while exposing result previews, target/final URLs, fallback diagnostics, and error metadata; threaded matching `retrieval_action` metadata into frontend observability tool-call events; and hardened invalid-URL handling so malformed requests do not break route contracts.

Task:
Keep `web_search` and `web_crawl` as backend primitives, but map them to richer user-visible retrieval action records and metadata.

Context:
You do not need new low-level tools to get OpenAI-like transparency. What you need is a normalization layer that translates existing tool invocations into frontend-facing action payloads with previews, target URLs, result counts, and similar diagnostics. This preserves backend simplicity while improving UX and debuggability.

Where to Look / Add:
- `backend/app/tools/web_search.py`
- `backend/app/tools/web_crawl.py`
- `src/core/telemetry/observability-logger.ts`

How to Test:
- `pytest backend/tests/tools/test_web_search_tool.py -q`
- `pytest backend/tests/tools/test_web_crawl_tool.py -q`
- `npm run test -- src/tests/frontend-api/observability-correlation.test.ts`
Success looks like canonical tools still returning stable normalized outputs while the observability layer exposes richer action metadata on top. We know this section is working when low-level tool contracts stay unchanged but the frontend-facing traces become more descriptive and still correlate correctly.

Completion Note:
Completed with `pytest backend/tests/tools/test_web_search_tool.py -q`, `pytest backend/tests/tools/test_web_crawl_tool.py -q`, `npm run test -- src/tests/frontend-api/observability-correlation.test.ts`, `npm run typecheck`, `npm run test`, `npm run build`, and `pytest backend/tests -q`.

## Section 17: Assemble Source Registry During Execution

✓ Completed: Added a runtime source registry that merges explicit source payloads, search-result sources, and crawl-derived consulted pages into one deduplicated registry; normalizes redirect aliases so citations resolve against final URLs consistently; and parses both structured and JSON-encoded tool outputs during runtime assembly.

Task:
Aggregate consulted URLs into a normalized source registry during runtime execution and attach cited or consulted subsets to final outputs.

Context:
Search results and crawled pages already contain most of the metadata you need for a `sources` list. The missing piece is a runtime-level registry that deduplicates URLs, handles redirects/final URLs, and keeps enough metadata for both answer citations and a broader consulted-source panel. This should be assembled during execution, not reconstructed later from logs.

Where to Look / Add:
- `backend/agent/runtime.py`
- `backend/app/contracts/web_search.py`
- `backend/app/contracts/web_crawl.py`

How to Test:
- `pytest backend/tests/agent/test_runtime.py -q`
Success looks like runtime execution accumulating a deduplicated consulted-source registry across searches, crawls, and redirects. We know this section is working when repeated URLs collapse into stable source records and cited answers can reference those records consistently.

Completion Note:
Completed with `npm install`, `pytest backend/tests/agent/test_runtime.py -q`, `npm run typecheck`, `npm run test`, `npm run build`, and `pytest backend/tests -q`.

## Section 18: Render Inline Citations And Sources In The Frontend

✓ Completed: Threaded structured answers through frontend run completion events, added citation-aware answer segmentation/rendering with clickable inline links plus a dedicated source list panel, and kept live/history views compatible by deriving rich answer state from canonical run events while preserving plain-text fallbacks.

Task:
Replace plain-text final-answer rendering with citation-aware answer rendering and a visible source list.

Context:
The current UI treats the answer as a plain string, which prevents clickable citations and makes provenance invisible. Introduce a rendering path that turns answer text plus span annotations into DOM output with safe links, and add a dedicated source list panel or footer for consulted pages. Keep the presentation readable in both live-run and history views.

Where to Look / Add:
- `src/frontend/client/app.ts`
- `public/index.html`
- `src/frontend/client/`

How to Test:
- `npm run test -- src/tests/frontend/state.test.ts`
- `npm run test -- src/tests/frontend/timeline.test.ts`
Success looks like the final answer rendering clickable inline citations and a readable source list in both active and historical views. We know this section is working when rendered citations point to the expected URLs/titles and the answer no longer needs to be displayed as plain text only.

Completion Note:
Completed with `npm run test -- src/tests/frontend/state.test.ts`, `npm run test -- src/tests/frontend/timeline.test.ts`, `npm run typecheck`, `npm run test`, and `npm run build`.

## Section 19: Make History Storage Citation-Aware

✓ Completed: Run-history storage now truncates completion payloads structurally instead of dropping them wholesale, keeping stored structured answers renderable with valid citation spans and non-orphaned source references after payload limits are applied, with integration coverage proving truncated history snapshots still reload and segment safely.

Task:
Update run-history persistence and truncation logic so structured answers, citation spans, and source lists are retained safely.

Context:
The current history store knows how to truncate payloads and final-answer strings, but citation-rich outputs introduce new consistency risks. Truncation must not leave invalid span indices, orphaned source references, or partially stored citation metadata that breaks the renderer. Treat storage integrity as part of the contract, not an implementation detail.

Where to Look / Add:
- `src/frontend/run-history/store.ts`
- `src/frontend/contracts/run-events.ts`
- `src/tests/frontend-api/`

How to Test:
- `npm run test -- src/tests/frontend-api/run-history.integration.test.ts`
Success looks like stored runs preserving citation-aware answers without producing invalid spans or orphaned sources after truncation. We know this section is working when history snapshots can be reloaded and rendered safely even for large answers and payloads.

Completion Note:
Completed with `npm run test -- src/tests/frontend-api/run-history.integration.test.ts`, `npm run typecheck`, `npm run test`, and `npm run build`.

## Section 20: Enforce Safe Citation URL Exposure

✓ Completed: Hardened backend runtime source assembly so only normalized safe `http`/`https` URLs enter the source registry, redirect/final URL aliases resolve through the same normalized lookup path, citations must resolve against policy-cleared source records before emission, and fallback URL-like citation titles are replaced by stronger explicit source metadata when available.

Task:
Ensure citation URLs and source links are emitted only from normalized, policy-cleared source records.

Context:
Adding clickable citations increases the risk of exposing malformed, unsafe, or policy-denied URLs if the renderer trusts raw model output. Restrict citation emission to source records that have already passed your URL and network safety controls, and make sure redirects/final URLs are handled consistently. This should prevent citation rendering from becoming a side door around existing fetch safety rules.

Where to Look / Add:
- `src/core/policy/url-policy.ts`
- `src/core/network/redirect-guard.ts`
- `backend/agent/runtime.py`

How to Test:
- `npm run test -- src/tests/safety/url-policy.test.ts`
- `npm run test -- src/tests/fetch/fetch.safety-compliance.integration.test.ts`
Success looks like only normalized, policy-cleared URLs becoming clickable citations or source links in rendered output. We know this section is working when unsafe or malformed URLs are rejected before they can appear as citations, even if upstream content tries to surface them.

Completion Note:
Completed with `npm install`, `npm run test -- src/tests/safety/url-policy.test.ts`, `npm run test -- src/tests/fetch/fetch.safety-compliance.integration.test.ts`, `pytest backend/tests/agent/test_runtime.py -q`, `npm run typecheck`, `npm run test`, `npm run build`, and `pytest backend/tests -q`.

## Section 21: Lock Down Citation And Output Coverage

✓ Completed: Added regression coverage for citation-rich legacy backend success envelopes and citation-aware `run_complete` SSE payloads, including malformed completion payload rejection in the stream client, then re-ran the full repo validation loop cleanly.

Task:
Add full contract, rendering, and regression coverage for citation-aware answers, source lists, and retrieval-action stream events.

Context:
This feature crosses backend contracts, SSE transport, history persistence, and frontend rendering, so it is especially vulnerable to schema drift. The final verification pass should cover happy paths, malformed citation data, truncation behavior, and live/history rendering consistency. Finish by running the full repo validation loop so the new output model lands cleanly.

Where to Look / Add:
- `src/tests/frontend-api/`
- `src/tests/frontend/`
- `backend/tests/agent/`
- `backend/tests/api/`

How to Test:
- `npm run typecheck`
- `npm run test`
- `npm run build`
- `pytest backend/tests -q`
Success looks like citation-aware answers, source lists, and retrieval action events all surviving full-suite validation across contracts, runtime, persistence, and rendering. We know this section is working when focused citation tests pass and the full repo validation loop still succeeds without regressions.

Completion Note:
Completed with `npm install`, `npm run test -- src/tests/frontend-api/runs.stream.test.ts`, `pytest backend/tests/api/test_agent_run_route.py -q`, `npm run typecheck`, `npm run test`, `npm run build`, and `pytest backend/tests -q`.
