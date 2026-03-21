# Implementation Plan
Current Section: 7

## Section 1: Extend Web Crawl Contracts For Objective-Driven Extraction ✓

Task:
Add an optional `objective` input to `web_crawl` and expand the crawl success payload to support focused excerpt-style outputs without breaking existing normalized crawl behavior.

Context:
Your current crawl contract only accepts a URL and returns truncated full-page text plus markdown, which forces the agent to reason over irrelevant content on long pages. The first step is to make the crawl surface objective-aware while keeping the existing `web_crawl` tool name, safety behavior, and success/error envelopes stable. This should remain backward-compatible for callers that do not supply an objective.

Where to Look / Add:
- `backend/app/contracts/web_crawl.py`
- `backend/app/tools/web_crawl.py`
- `backend/tests/tools/test_web_crawl_tool.py`
- `backend/tests/crawler/test_http_worker.py`

How to Test:
- `pytest backend/tests/tools/test_web_crawl_tool.py -q`
- `pytest backend/tests/crawler/test_http_worker.py -q`
Success looks like `web_crawl` accepting both legacy URL-only requests and new objective-bearing requests while still validating cleanly at the contract layer. We know this section is working when objective-aware inputs produce contract-valid success payloads and legacy callers remain unaffected.

Completion Note:
Do not end this section until it has been thoroughly tested.
Completed: Added optional `objective` request support, added contract-valid excerpt payload fields to `web_crawl` success responses, preserved legacy URL-only behavior, and verified with `pytest backend/tests/tools/test_web_crawl_tool.py -q` and `pytest backend/tests/crawler/test_http_worker.py -q`.

Commit Note:
Commit and push this section atomically once its tests pass.

## Section 2: Add Passage Chunking And Objective Scoring To Crawl Extraction ✓

Task:
Implement passage segmentation and objective-based excerpt selection so crawl results can return the most relevant page segments instead of only raw full-page content.

Context:
This is the main accuracy lift. The current extraction path in `web_crawl` returns whatever the extractor produces and then applies a hard character truncation, which is cheap but noisy on long documents. Use a lightweight in-memory approach: split extracted content into passages, do lexical prefiltering first, then apply selective embedding-based ranking only when the page is long enough and an objective is present. This keeps the feature useful without forcing expensive full-page embedding on every crawl.

Where to Look / Add:
- `backend/app/tools/web_crawl.py`
- `backend/app/crawler/extractor.py`
- `backend/tests/tools/test_web_crawl_tool.py`
- `backend/tests/crawler/test_extractor.py`

How to Test:
- `pytest backend/tests/tools/test_web_crawl_tool.py -q`
- `pytest backend/tests/crawler/test_extractor.py -q`
Success looks like long-page crawl responses surfacing concise, relevant excerpts when an objective is present, while fallback behavior remains sensible when no strong match exists. We know this section is working when tests can prove objective-aware selection prefers the right passages and still preserves stable output for non-objective requests.

Completion Note:
Do not end this section until it has been thoroughly tested.
Completed: Added passage segmentation with duplicate suppression, objective-aware lexical scoring with long-page cosine reranking, and lead-passage fallback excerpts, then verified with `pytest backend/tests/tools/test_web_crawl_tool.py -q`, `pytest backend/tests/crawler/test_extractor.py -q`, `pytest backend/tests/crawler/test_http_worker.py -q`, `npm run typecheck`, `npm run test`, and `npm run build`.

Commit Note:
Commit and push this section atomically once its tests pass.

## Section 3: Add Search Reranking And LLM-Optimized Excerpts ✓

Task:
Upgrade `web_search` so it returns better agent-facing excerpts and more useful result ordering than the raw provider ranking alone.

Context:
Your current search layer is close to a normalized Serper wrapper, which is a solid base but does not yet optimize for downstream agent reasoning. The next lift is to improve the quality of snippets and ranking before the agent decides which pages to crawl. Keep the provider payload internal and preserve current search contracts where possible, but introduce a post-provider reranking and excerpt-construction layer tuned for model consumption.

Where to Look / Add:
- `backend/app/tools/web_search.py`
- `backend/app/contracts/web_search.py`
- `backend/app/providers/serper_client.py`
- `backend/tests/tools/test_web_search_tool.py`

How to Test:
- `pytest backend/tests/tools/test_web_search_tool.py -q`
- `npm run test -- src/tests/search/search.integration.test.ts`
Success looks like search responses containing tighter, more relevant excerpts and more helpful result ordering for research prompts. We know this section is working when fixtures show the reranking layer preferring pages that are more likely to answer the prompt and the updated snippet payloads remain contract-valid.

Completion Note:
Do not end this section until it has been thoroughly tested.
Completed: Added query-aware rerank scoring to normalized search results, enriched Serper snippets with provider metadata, rewrote excerpts toward query-matching passages, and verified with `pytest backend/tests/tools/test_web_search_tool.py -q`, `npm run test -- src/tests/search/search.integration.test.ts`, `npm install`, `npm run typecheck`, `npm run test`, and `npm run build`.

Commit Note:
Commit and push this section atomically once its tests pass.

## Section 4: Make Retrieval Policy Controls More Intelligent And Automatic ✓

Task:
Extend the existing domain and freshness policy system so the agent can infer and apply tighter source controls from prompt intent instead of relying only on explicit user inputs.

Context:
You already have retrieval controls for domain scope and freshness, but the current system depends on callers supplying them directly. Accuracy improves when the runtime can automatically recognize prompts like “official docs only,” “latest filing,” or “recent coverage” and translate them into policy constraints before search begins. This should remain bounded and transparent so policy inference does not become unpredictable prompt magic.

Where to Look / Add:
- `src/core/policy/retrieval-controls.ts`
- `backend/agent/runtime.py`
- `backend/agent/prompts.py`
- `backend/tests/agent/test_runtime.py`

How to Test:
- `pytest backend/tests/agent/test_runtime.py -q`
- `npm run test -- src/tests/search-controls.integration.test.ts`
- `npm run test -- src/tests/fetch-controls.integration.test.ts`
Success looks like prompts with clear recency or source-governance intent producing consistent retrieval policies without requiring manual include/exclude settings every time. We know this section is working when runtime tests and control integrations show the inferred policies being applied deterministically and safely.

Completion Note:
Do not end this section until it has been thoroughly tested.
Completed: Added deterministic prompt-intent inference for freshness and official-source domain scope, threaded effective retrieval policy into runtime config and system prompts, and verified with `pytest backend/tests/agent/test_runtime.py -q`, `npm run test -- src/tests/search-controls.integration.test.ts`, `npm run test -- src/tests/fetch-controls.integration.test.ts`, `npm run typecheck`, `npm run test`, and `npm run build`.

Commit Note:
Commit and push this section atomically once its tests pass.

## Section 5: Teach The Agent Runtime To Use Objective-Driven Retrieval Strategically

Task:
Update runtime and prompt guidance so agentic and deep-research runs use focused objectives in `web_crawl` and make deliberate use of improved search outputs and retrieval policy controls.

Context:
The extraction and search upgrades will not materially improve answers unless the runtime uses them deliberately. Right now the system prompt and tool wiring still describe `web_crawl` as a generic page fetch and `web_search` as a generic search primitive, which encourages broad reading and weak source selection. The runtime should preserve the same bounded tool model while steering the agent to search and open pages with clear purposes tied to the user prompt and inferred policy constraints.

Where to Look / Add:
- `backend/agent/prompts.py`
- `backend/agent/runtime.py`
- `backend/tests/agent/test_runtime.py`

How to Test:
- `pytest backend/tests/agent/test_runtime.py -q`
- `pytest backend/tests/tools/test_web_crawl_tool.py -q`
- `pytest backend/tests/tools/test_web_search_tool.py -q`
Success looks like runtime fixtures showing the agent issuing more targeted search and crawl calls with explicit objectives and tighter source selection. We know this section is working when prompt and runtime changes improve retrieval behavior without changing canonical tool names or breaking existing mode/profile bounds.

Completion Note:
Do not end this section until it has been thoroughly tested.
Completed: ✓ Updated runtime prompt wiring so agentic and deep-research runs receive explicit retrieval strategy guidance, require objective-bearing `web_crawl` calls, reinforce excerpt-driven search triage, and verified with `pytest backend/tests/agent/test_runtime.py -q`, `pytest backend/tests/tools/test_web_crawl_tool.py -q`, `pytest backend/tests/tools/test_web_search_tool.py -q`, `npm install`, `npm run typecheck`, `npm run test`, and `npm run build`.

Commit Note:
Commit and push this section atomically once its tests pass.

## Section 6: Add Granular Claim And List-Item Basis Verification

Task:
Expand answer assembly so individual claims or list elements can carry their own supporting basis instead of relying only on top-level source attribution.

Context:
This does not improve retrieval recall directly, but it improves factual trust and makes it easier to detect weak synthesis. Your current structured answer and source registry work provides a good foundation for this because sources and citation spans already exist. The next step is to attach evidence more precisely to each answer segment or structured list item so users can audit the response at finer granularity.

Where to Look / Add:
- `backend/agent/types.py`
- `backend/agent/runtime.py`
- `src/frontend/contracts.ts`
- `backend/tests/agent/test_runtime.py`

How to Test:
- `pytest backend/tests/agent/test_runtime.py -q`
- `npm run test -- src/tests/frontend-api/routes.contracts.test.ts`
Success looks like answer payloads preserving per-claim or per-item evidence references without breaking the existing structured answer contract. We know this section is working when tests can assert that multiple claims in one response do not collapse onto a single generic citation blob.

Completion Note:
Do not end this section until it has been thoroughly tested.
Completed: ✓ Added optional per-claim and per-list-item `basis` evidence to structured answers, validated basis citations against the safe source registry, preserved basis data through frontend contracts and run-history truncation, and verified with `npm install`, `npm run typecheck`, `npm run test`, `npm run build`, `pytest backend/tests/agent/test_runtime.py -q`, and `npm run test -- src/tests/frontend-api/routes.contracts.test.ts`.

Commit Note:
Commit and push this section atomically once its tests pass.

## Section 7: Expand Research Progress Streaming For Retrieval Transparency

Task:
Add richer progress and retrieval-state events so long-running research can show what the agent is searching, crawling, validating, and synthesizing in real time.

Context:
This is not a core retrieval primitive, but it becomes much more important as search and crawl get smarter and slower. Better streaming makes it easier to debug retrieval quality and helps users understand whether the agent is still gathering evidence or is stuck. Keep the event model typed and bounded so the progress trace remains useful without turning into raw internal logs.

Where to Look / Add:
- `src/frontend/contracts/run-events.ts`
- `src/frontend/routes/runs.ts`
- `src/frontend/client/state.ts`
- `src/tests/frontend-api/runs.stream.test.ts`

How to Test:
- `npm run test -- src/tests/frontend-api/run-events.contracts.test.ts`
- `npm run test -- src/tests/frontend-api/runs.stream.test.ts`
- `npm run test -- src/tests/frontend-api/run-history.integration.test.ts`
Success looks like live and replayed run streams exposing meaningful retrieval milestones such as search reranking, objective crawl selection, verification, and synthesis. We know this section is working when the frontend can render these stages coherently and history replay preserves them without schema drift.

Completion Note:
Do not end this section until it has been thoroughly tested.

Commit Note:
Commit and push this section atomically once its tests pass.

## Section 8: Validate Objective-Driven Retrieval Accuracy And Regression Bounds

Task:
Add focused regression coverage for objective-driven extraction, improved search excerpts, and automatic retrieval policy behavior before the final integrated validation pass.

Context:
These retrieval changes affect evidence quality directly, so they need a targeted regression phase before the full end-to-end verification loop. In particular, guard against regressions in crawl truncation, source extraction, runtime tool budgets, and route-layer assumptions about `web_crawl` and `web_search` payload shapes. This section should prove the retrieval stack is materially better and still bounded before broader UI and answer-validation checks.

Where to Look / Add:
- `backend/tests/tools/`
- `backend/tests/agent/`
- `src/tests/frontend-api/`
- `src/tests/frontend/`

How to Test:
- `pytest backend/tests/tools/test_web_crawl_tool.py -q`
- `pytest backend/tests/tools/test_web_search_tool.py -q`
- `pytest backend/tests/agent/test_runtime.py -q`
Success looks like the upgraded retrieval flow passing focused backend and integration regressions without contract or safety drift. We know this section is working when targeted fixtures show better evidence selection, tighter excerpts, and consistent policy application while bounded runtime behavior remains intact.

Completion Note:
Do not end this section until it has been thoroughly tested.

Commit Note:
Commit and push this section atomically once its tests pass.

## Section 9: Run A Final Accuracy-Focused Validation Pass Across Search, Crawl, And Answering

Task:
Validate the combined impact of objective-driven crawl, improved search excerpts, smarter retrieval policy use, granular basis, and richer progress events through targeted regressions and the full repo verification loop.

Context:
These features interact: better search changes which pages get crawled, objective-driven crawl changes what evidence is seen, and granular basis changes how answers are assembled and rendered. The final pass should confirm the combined system is more accurate without regressing safety, contracts, or latency bounds beyond what is acceptable for each mode. Treat this as a feature-integration gate, not a cleanup step.

Where to Look / Add:
- `backend/tests/agent/`
- `backend/tests/tools/`
- `src/tests/frontend-api/`
- `src/tests/frontend/`

How to Test:
- `npm run typecheck`
- `npm run test`
- `npm run build`
- `pytest backend/tests -q`
Success looks like the retrieval stack passing both focused accuracy-oriented tests and the full project validation loop with stable contracts and bounded behavior. We know this section is working when the integrated system shows better evidence selection and explanation quality in fixtures while all required checks still pass.

Completion Note:
Do not end this section until it has been thoroughly tested.

Commit Note:
Commit and push this section atomically once its tests pass.
