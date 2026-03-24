# OpenAI Web Search Parity Design

Date: 2026-03-23
Status: Approved design
Scope: Align the current `quick`, `agentic`, and `deep_research` run modes with the product semantics described in OpenAI's web search guidance while keeping the existing custom retrieval stack.

## Goal

Preserve the current stack built around custom `web_search` and `web_crawl` tools, but make each run mode behave like a distinct product category rather than three budget variations of the same runtime.

Target categories:

- `quick`: non-agentic web search with one fixed retrieval pipeline and one final model call
- `agentic`: bounded reasoning-driven search and crawl over custom tools
- `deep_research`: long-running background research with explicit planning, repeated retrieval waves, and final synthesis

## Current State

### Quick

Current behavior:

- Runs one `web_search` call
- Synthesizes an answer directly from search results and snippets
- Does not open top pages before answering
- Does not use a final LLM answer pass

Assessment:

- This is fast and non-agentic, but it falls short of the target semantics because it stops at search snippets instead of grounding the answer in page content.

### Agentic

Current behavior:

- Uses a bounded agent loop with `web_search` and `web_crawl`
- Applies retrieval policy inference and prompt guidance
- Uses constrained search and crawl budgets

Assessment:

- This already matches the intended agentic-search shape reasonably well.

### Deep Research

Current behavior:

- Uses the same bounded agent loop as `agentic`
- Increases timeout, tool-call budget, search result cap, and crawl budget
- Still runs as one synchronous backend execution

Assessment:

- This is not yet a true deep-research product shape.
- It is currently a larger `agentic` profile, not a separate research system.

## Product Parity Gaps

- `quick` does not open the top results before answering.
- `quick` does not perform one final model synthesis pass over retrieved evidence.
- `deep_research` is not a distinct runtime shape.
- `deep_research` does not support several-minute background execution as a first-class flow.
- `deep_research` does not perform explicit planning, retrieval waves, evidence verification, or contradiction handling as dedicated stages.
- Current deep-research budgets are too small to credibly represent extended investigation.

## Design Decisions

### 1. Preserve the Current Retrieval Stack

Do not migrate to OpenAI-native web search or OpenAI-managed deep-research models as the primary runtime path.

Rationale:

- The goal is product parity, not provider parity.
- The current stack already has custom `web_search` and `web_crawl` behavior, retrieval policy inference, domain scoping, and event tracing.
- Migrating to OpenAI-native deep-research models would conflict with the current custom-tool architecture and introduce a separate capability surface.

### 2. Make the Three Modes Truly Distinct

The three modes must have different execution shapes:

- `quick` is a deterministic retrieval pipeline
- `agentic` is a bounded tool-using agent
- `deep_research` is a background research orchestrator

Do not represent `deep_research` as a larger `agentic` budget profile.

### 3. Keep Runtime Paths Explicit

Prefer direct function calls and small orchestration modules over generic runners or hidden framework indirection.

This aligns with repository guidance to:

- keep runtime orchestration split into small task-focused modules
- separate routers, services, frontend, and backend responsibilities
- avoid monolithic runtime files

## Target Runtime Semantics

### Quick

`quick` should be a fixed function sequence with no agent loop.

Target behavior:

1. Infer retrieval policy from the prompt.
2. Run `web_search` once.
3. Select the top 3 allowed results using deterministic rules.
4. Run `web_crawl` on those URLs with bounded extraction.
5. Build one evidence bundle from the crawled pages.
6. Make one final LLM call to return the structured answer.

Rules:

- No model-driven planning
- No iterative tool use
- No tool-choice loop
- No LangChain agent runtime
- A single final model call is allowed and required

Model guidance:

- Use a non-reasoning or low-reasoning OpenAI model for the final answer pass.
- LangChain may be used only for a structured response at the end if it remains a direct single-call wrapper rather than an agent path.

### Agentic

`agentic` remains the bounded synchronous reasoning mode.

Target behavior:

- Use the current `web_search` and `web_crawl` tools
- Allow model-managed search and crawl sequencing
- Keep bounded budgets and prompt guidance
- Preserve the existing synchronous request-response behavior

Model guidance:

- Continue using a reasoning-capable model with normal tool calling.

### Deep Research

`deep_research` becomes a dedicated several-minute background research workflow.

Target behavior:

1. Create a background research job.
2. Plan sub-questions and evidence goals.
3. Execute repeated search and crawl waves across those goals.
4. Deduplicate sources and extracted evidence.
5. Identify conflicting claims and schedule targeted verification passes.
6. Run final synthesis after evidence coverage reaches a stopping threshold or job budget expires.
7. Persist progress and expose it through run status and event history.

Rules:

- Must not share the same execution shape as `agentic`
- Must support several-minute execution
- Must survive disconnects from the initiating client
- Must persist intermediate progress
- Must support staged progress reporting

Model guidance:

- Use `gpt-5` with `reasoning_effort=high` for planning, verification, and/or final synthesis stages when staying on the custom tool stack.
- Do not make OpenAI specialized deep-research models the primary runtime dependency for this architecture.

## Proposed Backend Architecture

### Quick Path

Add focused quick-runtime modules:

- `backend/agent/quick_runtime.py`: entrypoint for the fixed quick pipeline
- `backend/agent/quick_selection.py`: top-result selection and fallback rules
- `backend/agent/quick_evidence.py`: evidence bundle assembly from crawled pages
- `backend/agent/answer_synthesis.py`: one final structured-answer model call

Responsibilities:

- `quick_runtime.py` coordinates the fixed sequence directly
- `quick_selection.py` decides which search results to crawl
- `quick_evidence.py` produces a bounded answer-ready prompt context
- `answer_synthesis.py` returns the final structured answer

### Agentic Path

Keep the existing agent runtime and retrieval policy flow, with only minor refactoring if needed to maintain clear boundaries.

Likely existing touchpoints:

- `backend/agent/runtime.py`
- `backend/agent/runtime_execution.py`
- `backend/agent/runtime_policy.py`
- `backend/agent/prompts.py`

### Deep Research Path

Add dedicated deep-research modules:

- `backend/agent/deep_research_runtime.py`: background job coordinator
- `backend/agent/deep_research_planning.py`: sub-question and objective planning
- `backend/agent/deep_research_execution.py`: repeated search/crawl waves
- `backend/agent/deep_research_verification.py`: contradiction checks and evidence validation
- `backend/agent/deep_research_store.py`: persisted state and checkpoints

Responsibilities:

- keep long-running orchestration out of the current synchronous runtime module
- persist research state outside ephemeral request scope
- separate planning, execution, and verification concerns into atomic files

## API and Runtime Behavior

### Shared API Surface

Keep the single run API concept, but route each mode to the correct runtime path behind the scenes.

### Quick API Behavior

- Request remains synchronous
- Response returns completed answer, sources, and metadata
- Response must reflect degraded retrieval when some top results fail to crawl

### Agentic API Behavior

- Keep current synchronous response pattern
- Continue returning answer, sources, and metadata

### Deep Research API Behavior

Deep research should no longer behave like a synchronous backend execution.

Target behavior:

- submit a run and receive a queued or running job handle
- continue progress through events and stored run history
- allow several-minute execution windows
- return final output only when the job reaches completion

Recommended states:

- `queued`
- `running`
- `blocked`
- `completed`
- `failed`
- `timed_out`

## Retrieval and Evidence Strategy

### Quick

- Search once
- Crawl only the top fixed fanout, default 3
- Prefer direct-answer pages over broad background pages
- Assemble a compact evidence packet for one answer pass

### Agentic

- Preserve current retrieval-policy-driven search and crawl guidance
- Maintain bounded tool budgets
- Use excerpts to decide whether pages are worth opening

### Deep Research

- Plan multiple sub-questions
- Run repeated retrieval waves
- Track source diversity and evidence overlap
- Escalate contradictory or weakly-supported claims for targeted verification
- Stop based on budget, coverage, or diminishing returns

## Error Handling

### Quick

- Fail fast on invalid prompt or invalid retrieval request
- If search returns no results, return a typed empty-results response path
- Allow partial crawl success
- If one or more crawls fail, answer from remaining evidence and record degraded retrieval
- If all crawls fail, return a typed runtime failure rather than a low-confidence fabricated answer

### Agentic

- Preserve current bounded-tool failure behavior

### Deep Research

- Persist intermediate progress before expensive steps
- Distinguish terminal failure from temporary blockage
- Support resumable or restartable execution where possible
- Record verification failures and contradiction resolution attempts in event history

## Testing Strategy

### Quick

- unit tests for deterministic result selection
- unit tests for evidence assembly
- unit tests for final answer synthesis input construction
- integration tests proving `quick` never enters the agent path
- integration tests covering partial crawl failure and degraded answer generation

### Agentic

- regression tests proving current bounded tool usage and prompt guidance remain intact

### Deep Research

- unit tests for planning and verification stages
- integration tests for background lifecycle and persisted progress
- integration tests for long-running event history and completion
- tests for contradiction handling and targeted follow-up research

## Rollout Recommendation

Recommended implementation order:

1. Upgrade `quick` into the fixed search -> crawl -> answer pipeline.
2. Keep `agentic` stable while extracting any shared answer-synthesis helpers cleanly.
3. Build `deep_research` as a dedicated background runtime with persisted state and longer execution windows.

This order improves product parity immediately for `quick` without destabilizing `agentic`, then creates the correct architectural foundation for real deep research.

## Non-Goals

- Replacing the current custom search provider stack
- Converting all modes to OpenAI-native tools
- Treating deep research as only a prompt tweak or budget increase
- Expanding the current synchronous runtime into a monolithic all-mode orchestrator

## Final Recommendation

Implement three explicit runtime paths:

- `quick`: deterministic retrieval pipeline plus one final model synthesis call
- `agentic`: existing bounded agentic search flow
- `deep_research`: dedicated several-minute background investigation system

This achieves product-parity semantics with the OpenAI categories while preserving the current retrieval stack and honoring the repository's preference for explicit, small, focused runtime modules.
