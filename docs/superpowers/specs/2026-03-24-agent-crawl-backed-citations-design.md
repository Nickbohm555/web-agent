# Agent Crawl-Backed Citations Design

Date: 2026-03-24
Status: Approved design
Scope: Move final answer citations and sources into the primary agent response path by making the backend deterministically finalize answers from crawled evidence only.

## Goal

Ensure the shipped `final_answer`, `citations`, `basis`, and `sources` are built from evidence actually read through `web_crawl`, not reconstructed afterward from loosely structured agent messages or search payloads.

## Non-Goals

- Do not allow `web_search` snippets to appear as answer citations.
- Do not change `quick` mode in this design; this scope is for the agent-driven crawl-backed runtime path.
- Do not rely on prompt-only compliance for citation correctness.
- Do not keep placeholder-answer recovery as the main success path.
- Do not collapse the runtime into a larger monolithic orchestration module.

## Current State

Current behavior:

- The agent runs with `web_search` and `web_crawl`.
- After the run completes, the backend inspects raw runtime output and message payloads to recover `final_answer`, `citations`, and `sources`.
- Source extraction and citation recovery are handled as post-hoc parsing in `backend/agent/runtime_sources.py`.
- Placeholder answers can be replaced with a source summary after the fact if sources were found.

Problems:

- Citation correctness depends on framework message shape and model output shape.
- `web_search` and `web_crawl` evidence are not cleanly separated in the final-answer path.
- The backend can emit a successful answer even when the agent did not explicitly finish with valid crawl-backed support.
- The runtime source parsing layer is doing recovery work that should instead be represented as explicit runtime state.

## Design Decisions

### 1. `web_search` Is Discovery Only

`web_search` may help the agent choose what to crawl, but it must never provide answer citations or final `sources`.

Implications:

- Search results remain planning metadata.
- Only `web_crawl` can create answer-eligible evidence.

### 2. The Backend Owns Final Answer Construction

The agent does not ship the final cited answer directly.

Instead:

1. The agent performs search and crawl work.
2. Successful crawl outputs are normalized into a run-scoped evidence registry.
3. The agent ends by returning a structured selection payload identifying which crawled evidence supports the answer.
4. The backend finalizer deterministically builds `AgentStructuredAnswer` and `sources` from that registry and selection.

This makes the backend, not the model or framework serializer, the source of truth for citations.

### 3. Answer Finalization Must Be Explicit and Validated

The runtime should not infer a good answer from whatever happens to be in the final `AIMessage`.

Instead, the run must pass a finalization gate that validates:

- selected evidence exists in the crawl registry
- every cited source was actually crawled
- every emitted citation maps to selected crawl evidence
- returned `sources` is the exact cited-source closure

### 4. Runtime Modules Must Stay Small and Explicit

Add focused runtime modules instead of growing `backend/agent/runtime.py` or `backend/agent/runtime_execution.py` further.

Recommended modules:

- `backend/agent/runtime_evidence_registry.py`
- `backend/agent/runtime_evidence_selection.py`
- `backend/agent/runtime_answer_finalizer.py`
- `backend/agent/runtime_answer_validation.py`

## Target Runtime Flow

For `agentic` and any other agent-driven crawl-backed answer path:

1. The agent receives the user prompt and retrieval policy.
2. The agent uses `web_search` to discover candidate URLs.
3. The agent uses `web_crawl` with explicit objectives to read promising pages.
4. Each successful crawl is normalized into canonical evidence records in a run-scoped registry.
5. When ready to answer, the agent emits a structured selection payload that references only crawled source ids or chunk ids.
6. The backend answer finalizer reads the crawl registry plus the selection payload.
7. The backend builds `final_answer.text`, `final_answer.citations`, `final_answer.basis`, and `sources`.
8. The API response and run events use that finalized object directly.

## Evidence Registry Contract

The registry should contain only crawl-backed evidence records.

Recommended source-level fields:

- `source_id`
- `url`
- `title`
- `objective`
- `crawl_status`
- `selected_for_answer`
- `evidence_chunks`

Recommended chunk-level fields:

- `chunk_id`
- `text`
- `start_offset`
- `end_offset`
- `matched_objective`
- `usable_for_answer`

Notes:

- These records are backend-owned normalized data, not model-authored citations.
- The registry is per run and should be consumed by the finalization step before building `AgentRunResult`.

## Agent Output Contract

The agent's final output should be reduced to a deterministic selection signal instead of freeform citation authoring.

Preferred shape:

- `selected_source_ids`
- `selected_chunk_ids`

Optional richer shape if needed later:

- `claims`, where each claim references supporting `chunk_ids`

Rules:

- The agent may select only crawled evidence.
- The agent may not reference search-only results.
- If the agent returns unsupported ids, finalization fails.

The agent does not author the shipped answer text, citation spans, or `sources` list.

## Backend Finalization Contract

The backend finalizer is responsible for constructing:

- `final_answer.text`
- `final_answer.citations`
- `final_answer.basis`
- `sources`

from:

- the run-scoped crawl evidence registry
- the agent's final evidence-selection payload

The finalizer should be deterministic with respect to source and citation membership:

- only selected crawled evidence may appear
- every citation span must resolve to selected evidence
- every source in `sources` must be cited by `final_answer.citations` or by a citation nested under `final_answer.basis`

### Deterministic Answer Construction

The shipped answer text is backend-generated from the selected crawl chunks.

Initial deterministic strategy:

1. Order selected chunks by the agent-provided selection order, falling back to source order and chunk offsets.
2. Build one basis item per selected chunk using the normalized chunk text.
3. Build top-level `final_answer.text` by concatenating the basis texts with deterministic separators.
4. Compute citation spans from the inserted text offsets in the finalized string.
5. Build top-level citations as the ordered union of the basis citations.

Implications:

- No final freeform synthesis model call is required for this phase.
- Citation indices are computed by backend string assembly, not by model-authored offsets.
- The first implementation may produce rigid prose, but it guarantees deterministic crawl-backed membership and spans.

### `sources` Closure

Top-level `sources` is the exact deduplicated set of sources referenced by:

- `final_answer.citations`
- any citation nested under `final_answer.basis`

No additional searched or crawled sources may be included.

### Failure Mapping

When finalization fails because evidence selection is invalid, missing, or unresolved, the run should fail with:

- `category="tool_failure"`
- `retryable=False`

This keeps API behavior stable with the current failure family for unusable crawl outcomes while making the finalization gate strict.

## Failure Rules

Fail the run when any of the following occurs:

- the agent finishes without selecting crawled evidence
- the agent references evidence that is not present in the crawl registry
- crawl returned no usable answer evidence
- final citations cannot be resolved against selected crawl chunks
- backend deterministic answer assembly cannot produce a non-empty finalized answer
- final `sources` would include searched-but-not-crawled material

Do not recover these cases by:

- scraping arbitrary `AIMessage` payloads for citations as the main path
- summarizing sources as a fallback success path
- accepting search snippets as evidence

## Codebase Touchpoints

Primary touchpoints:

- `backend/agent/runtime_execution.py`
- `backend/agent/runtime_sources.py`
- `backend/agent/prompts.py`
- `backend/agent/schemas/__init__.py`
- `backend/api/schemas/agent_run.py`
- `src/frontend/routes/runs.ts`
- `src/frontend/client/answer-rendering.ts`

Expected runtime changes:

- insert backend finalization after `agent.invoke(...)` and before `AgentRunResult` construction
- shift `runtime_sources.py` away from being the primary citation-recovery path
- update prompts so the agent returns a selection payload rather than authoring final citations directly
- keep frontend contracts stable where possible by continuing to emit `AgentStructuredAnswer` and `sources`, but now from the finalizer

## Migration Strategy

### Phase 1: Add the Registry

- Introduce run-scoped crawl evidence models and storage.
- Populate them only from successful `web_crawl` results.

### Phase 2: Add Selection Output

- Update the system prompt and result parsing so the agent ends with a structured evidence-selection payload.

### Phase 3: Add Finalization

- Build a backend finalizer that consumes the registry plus selection payload and returns canonical `AgentStructuredAnswer` and `sources`.

### Phase 4: Remove Post-Hoc Recovery as Primary Path

- Keep compatibility parsing only as a temporary migration aid if needed.
- Remove placeholder-answer substitution and loose citation recovery as the default success path.

## Testing Strategy

Add or update tests to prove:

- searched-but-not-crawled URLs never appear in `citations` or `sources`
- a run fails when the agent answers without selecting crawl-backed evidence
- a run fails when selected ids do not exist in the crawl registry
- returned `sources` exactly match cited crawl-backed sources
- placeholder or summary fallback does not mask missing evidence
- final answer events and API responses carry the finalized structured answer object directly

## Recommendation

Adopt backend-owned finalization with crawl-only evidence and an agent selection payload.

This gives:

- deterministic citation membership
- clear separation between discovery and evidence
- reduced dependence on framework message serialization details
- a smaller, more explicit runtime architecture aligned with repository guidance
