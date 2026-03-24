# Phase 5: Evidence-Grounded Completion - Research

**Date:** 2026-03-24
**Status:** Complete
**Phase:** 5 - Evidence-Grounded Completion

## Question

What needs to be true in this repo for Deep Agents research to finish only when evidence-bearing subagent outputs have been normalized and judged sufficient, without changing the shipped `deep_research` API envelope?

## Sources Reviewed

- `.planning/ROADMAP.md`
- `.planning/REQUIREMENTS.md`
- `.planning/STATE.md`
- `AGENTS.md`
- `backend/agent/deep_research_runtime.py`
- `backend/agent/deep_research_execution.py`
- `backend/agent/deep_research_verification.py`
- `backend/agent/runtime_execution.py`
- `backend/agent/runtime_sources.py`
- `backend/agent/prompts.py`
- `backend/agent/schemas/deep_research.py`
- `backend/tests/agent/test_deep_research_runtime.py`
- `docs/superpowers/specs/2026-03-24-agent-crawl-backed-citations-design.md`
- LangChain Deep Agents overview: `https://docs.langchain.com/oss/python/deepagents/overview`
- LangChain Deep Agents backends: `https://docs.langchain.com/oss/python/deepagents/backends`
- LangChain built-in middleware: `https://docs.langchain.com/oss/python/langchain/middleware/built-in`

## Current Repo State

- `backend/agent/deep_research_runtime.py` is still a placeholder orchestrator. It plans, executes one wave, verifies once, marks `synthesizing`, and finalizes immediately.
- `backend/agent/deep_research_execution.py` does not yet run subagents; it only flips the stage to `searching` and increments `wave_count`.
- `backend/agent/deep_research_verification.py` does not evaluate evidence sufficiency; it only changes the stage to `verifying`.
- `backend/agent/schemas/deep_research.py` only tracks `sub_questions`, `sources`, `wave_count`, and `final_answer`. There is no normalized subagent-result state.
- `backend/agent/runtime_sources.py` already has useful normalization logic for sources and citations, but it is built for post-hoc agent/runtime parsing rather than Deep Agents subagent result contracts.

## Relevant External Constraints

- LangChain Deep Agents currently exposes `create_deep_agent(...)`, built-in planning, a built-in `task` tool for subagents, and pluggable backends for durable state. This matches the roadmap direction for the supervisor architecture.
- LangChain’s middleware docs currently show production-ready middleware patterns and explicitly support subagent middleware composition. The most relevant seam for this phase is validating and normalizing evidence immediately after model or subagent output, rather than scraping message content later.
- Deep Agents backends route filesystem state explicitly. That reinforces the repo instruction to keep runtime wiring explicit and split into small modules instead of letting one runtime file absorb policy, normalization, and completion logic.
- The current environment risk remains important: the local Python runtime reported during research was `3.9.13`, while the current `deepagents` package line expects Python `>=3.11`. If earlier phases do not upgrade the backend runtime before implementation, this phase should treat that as a prerequisite check.

## Key Planning Findings

### 1. Phase 5 should add explicit deep-research evidence models, not more loose `dict[str, Any]` parsing

The repo instructions require explicit Pydantic contracts when the shape is known. Phase 5 has a stable shape:

- a subanswer
- normalized search-result sources
- normalized crawl-result citations
- a completion/sufficiency decision

That means this phase should add focused Deep Research schema models instead of extending placeholder dictionaries inside `DeepResearchJob`.

### 2. Middleware should enforce the subagent contract, but supervisor code should own normalization

Middleware is the right place to remind or reject malformed subagent outputs before they are accepted by the supervisor. However, the supervisor should still normalize every accepted subagent result into backend-owned structures before synthesis.

Recommended split:

- middleware module: inject the required response shape and validate or reject missing evidence-bearing fields as soon as a subagent returns
- normalization module: coerce accepted subagent messages into typed repo-local models
- completion module: evaluate whether enough subquestions are answered well enough to synthesize

### 3. Search sources and crawl citations should be treated differently

The roadmap requires subagent outputs to include normalized search-result sources and crawl-result citations. The approved crawl-backed citation design says only crawl-backed evidence should drive shipped answer citations.

The clean reconciliation is:

- `search_sources`: planning and coverage metadata for the supervisor
- `crawl_citations`: answer-eligible evidence for the final shipped answer

That avoids using search snippets as final citations while still meeting the roadmap language for normalized search-result sources in subagent results.

### 4. Completion gating needs a real loop, not a one-pass verify step

`DEEP-04` and `RSCH-04` require the supervisor to continue researching until enough evidence exists. The current `verify_deep_research_job(...)` signature is a good seam, but it needs a loop contract such as:

- inspect normalized subagent results
- determine which planned subquestions are still missing sufficient evidence
- request another research pass only for unresolved subquestions
- stop when all planned subquestions are sufficiently answered or when a bounded retry budget is exhausted

### 5. Keep runtime modules small

`AGENTS.md` explicitly forbids letting runtime orchestration grow monolithic. Phase 5 should not dump all logic into `deep_research_runtime.py`.

Recommended new focused modules:

- `backend/agent/deep_research_subagent_middleware.py`
- `backend/agent/deep_research_result_normalization.py`
- `backend/agent/deep_research_completion.py`
- `backend/agent/deep_research_finalization.py`

## Recommended Plan Shape

### Plan 05-01

Define the evidence-bearing subagent contract and middleware enforcement:

- add Deep Research result schemas
- add a middleware helper that enforces `subanswer`, `search_sources`, and `crawl_citations`
- update execution/prompt wiring so subagents return that structure
- add tests that malformed subagent outputs are rejected or marked unusable

### Plan 05-02

Define supervisor extraction, sufficiency gating, and final answer completion:

- normalize accepted subagent results into backend-owned structures
- evaluate sufficiency across planned subquestions
- loop until enough evidence exists or a bounded retry budget is exhausted
- synthesize a final answer with normalized evidence embedded in message content while keeping the current top-level API envelope unchanged

## Risks

- If middleware enforcement is prompt-only and not validated after the fact, malformed subagent outputs will still leak through.
- If `deep_research_runtime.py` absorbs normalization, loop control, and finalization directly, it will violate repo structure guidance and become hard to test.
- If search snippets are allowed to become final citations, Phase 5 will conflict with the approved crawl-backed citation design.
- If sufficiency criteria are subjective, tests will be weak. The gate needs concrete measurable rules such as non-empty subanswer text plus at least one usable evidence-bearing reference per unresolved subquestion.
- If the runtime remains on Python `3.9.x` when Deep Agents implementation starts, the docs-aligned package line for this architecture will not be installable.

## Validation Architecture

Phase 5 is backend-only and should be validated primarily with targeted pytest coverage.

Recommended command layers:

- quick loop: `pytest backend/tests/agent/test_deep_research_runtime.py`
- contract loop: `pytest backend/tests/agent/test_runtime.py backend/tests/agent/test_deep_research_runtime.py`
- broader backend confidence: `pytest backend/tests/agent backend/tests/api`

Minimum scenarios to cover:

- malformed subagent result fails the evidence contract
- normalized subagent result carries both search-source metadata and crawl-citation evidence
- supervisor does not synthesize while any required subquestion lacks sufficient evidence
- supervisor requests additional research passes for unresolved subquestions
- final deep-research response keeps the existing top-level API fields while evidence remains embedded in `final_answer`

## Recommendation

Proceed with two execution plans:

1. Add the subagent evidence contract and middleware enforcement.
2. Add supervisor normalization, sufficiency looping, and final completion gating.
