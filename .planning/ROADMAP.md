# Roadmap: Web Agent

## Overview

This roadmap turns the current placeholder deep-research path into a LangChain Deep Agents implementation built around `create_deep_agent(...)`, with doc-aligned backend routing for planning artifacts, `langgraph-checkpoint-postgres` for durable thread resume, Deep Agents subagent fan-out over the existing retrieval stack, and final answers gated on normalized evidence without changing the current top-level API envelope.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Tool Contract Alignment** - Rename the currently exposed open-page tool contract from `web_crawl` to `open_url` and align retrieval names across all modes.
- [ ] **Phase 2: Deep Agents Run Lifecycle** - Replace the placeholder deep-research flow with a `create_deep_agent(...)` supervisor that can clarify and resume.
- [ ] **Phase 3: Deep Agents Persistence Backbone** - Use Deep Agents backends plus `langgraph-checkpoint-postgres` for durable planning state and inspectable progress.
- [x] **Phase 4: Deep Agents Research Fan-Out** - Run plan-derived subquestions through Deep Agents subagents that return subanswers plus normalized evidence from existing retrieval behavior. (completed 2026-03-24)
- [ ] **Phase 5: Evidence-Grounded Completion** - Use middleware as an enforcement and normalization layer so synthesis only completes once evidence from each subagent result is extracted and sufficient.

## Phase Details

### Phase 1: Tool Contract Alignment
**Goal**: Users can rely on one explicit retrieval contract across every runtime surface, with the currently exposed open-page or crawl tool name aligned from `web_crawl` to `open_url` while search remains `web_search`.
**Depends on**: Nothing (first phase)
**Requirements**: TOOL-01, TOOL-02
**Success Criteria** (what must be TRUE):
  1. User can access the search tool as `web_search` in quick mode.
  2. User can access the search tool as `web_search` and the currently exposed `web_crawl` page-opening contract is aligned to `open_url` in agentic mode.
  3. User can access the search tool as `web_search` and the currently exposed `web_crawl` page-opening contract is aligned to `open_url` in deep-research mode.
**Plans**: 3 plans

Plans:
- [ ] 01-01-PLAN.md — Align backend canonical tool bindings, prompt text, and parser tolerance to `web_search` + `open_url`.
- [ ] 01-02-PLAN.md — Align frontend contracts, observability, and event normalization to `open_url` while keeping `open_page`.
- [ ] 01-03-PLAN.md — Add queued deep-research, SSE/history, reducer, and timeline regressions for the renamed contract.

### Phase 2: Deep Agents Run Lifecycle
**Goal**: Users can start deep research through the LangChain Deep Agents architecture, centered on `create_deep_agent(...)`, with one clarification at a time and resume on the same thread.
**Depends on**: Phase 1
**Requirements**: DEEP-01, DEEP-02, DEEP-03
**Success Criteria** (what must be TRUE):
  1. User can start a `deep_research` run and the run is handled by a Deep Agents supervisor created via `create_deep_agent(...)` instead of the placeholder queued flow.
  2. User can receive no more than one clarifying question at a time before Deep Agents research fan-out begins.
  3. User can answer the clarifying question and continue the same `deep_research` thread without losing prior context.
**Plans**: 2 plans

Plans:
- [ ] 02-01: Replace the current deep-research entry path with a `create_deep_agent(...)`-based supervisor flow.
- [ ] 02-02: Add single-question clarification and same-thread resume handling around the Deep Agents run lifecycle.

### Phase 3: Deep Agents Persistence Backbone
**Goal**: Users can rely on doc-aligned Deep Agents persistence, with backend-routed planning artifacts and `langgraph-checkpoint-postgres` thread checkpoints that survive interruption and remain inspectable.
**Depends on**: Phase 2
**Requirements**: PLAN-01, PLAN-02, PLAN-03, PLAN-04
**Success Criteria** (what must be TRUE):
  1. User can start a deep-research run and a persistent high-level research plan is created in the Deep Agents filesystem surface before research workers begin.
  2. User can have the Deep Agents supervisor derive subquestions or research angles from that persisted plan.
  3. User can resume an interrupted deep-research run from `langgraph-checkpoint-postgres` thread checkpoints and persisted Deep Agents backend artifacts.
  4. User can inspect deep-research progress through persisted artifacts and logging without needing a new frontend surface.
**Plans**: TBD

Plans:
- [ ] 03-01: Configure the Deep Agents backend layer so HTTP runtime planning uses doc-aligned backends such as `StateBackend`, `StoreBackend`, or `CompositeBackend` instead of implying local-disk `FilesystemBackend` as the long-term server persistence path.
- [ ] 03-02: Add `langgraph-checkpoint-postgres` thread checkpointing plus inspectable progress logging and artifact persistence for resume.

### Phase 4: Deep Agents Research Fan-Out
**Goal**: Users can have plan-derived research threads executed in parallel by Deep Agents subagents that each answer an assigned subquestion and return reusable evidence from the existing retrieval stack.
**Depends on**: Phase 3
**Requirements**: RSCH-01, RSCH-02
**Success Criteria** (what must be TRUE):
  1. User can have the Deep Agents supervisor spawn parallel Deep Agents subagents for the subquestions produced by the plan.
  2. User can have each Deep Agents subagent use the same `web_search` and `open_url` retrieval behavior already supported by the project.
  3. User can have each Deep Agents subagent return a subanswer for its assigned subquestion together with search-result sources from `web_search` items and citations from crawled or opened pages.
  4. User can observe parallel research progress in persisted logs or artifacts as Deep Agents subagents complete their work.
**Plans**: 2 plans

Plans:
- [x] 04-01: Create the typed Deep Agents fan-out foundation: Wave 0 subagent tests, retrieval-tool injection, and a supervisor factory for parallel research delegation.
- [x] 04-02: Replace the placeholder deep-research wave executor with delegated subquestion execution, persisted progress, and normalized evidence aggregation.

### Phase 5: Evidence-Grounded Completion
**Goal**: Users receive a final deep-research answer only after middleware has enforced evidence-bearing subagent outputs and the supervisor has extracted and normalized those results for synthesis, while the top-level API shape stays unchanged.
**Depends on**: Phase 4
**Requirements**: RSCH-03, RSCH-04, DEEP-04, TOOL-03
**Success Criteria** (what must be TRUE):
  1. User can have each research subagent return an AI message whose content includes a subanswer plus normalized search-result sources and crawl-result citations, with middleware acting as the reminder and enforcement layer that keeps those fields present.
  2. User can have the Deep Agents supervisor extract and normalize the subanswer, search sources, and crawl citations from each subagent result before final synthesis.
  3. User can have the Deep Agents supervisor continue researching until it determines enough evidence exists to answer the original question deeply.
  4. User receives a final deep-research answer only after the supervisor decides the planned subquestions have been answered well enough and attaches normalized evidence in the final AI message content.
  5. User keeps the current top-level `deep_research` API response shape while evidence remains embedded inside AI message content.
**Plans**: TBD

Plans:
- [ ] 05-01: Add middleware that reminds and enforces Deep Agents subagents to return subanswers with normalized search sources and crawl citations.
- [ ] 05-02: Extract and normalize evidence from each subagent result for final supervisor synthesis and completion gating without changing the existing top-level response envelope.

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Tool Contract Alignment | 0/3 | Not started | - |
| 2. Deep Agents Run Lifecycle | 0/2 | Not started | - |
| 3. Deep Agents Persistence Backbone | 0/2 | Not started | - |
| 4. Deep Agents Research Fan-Out | 2/2 | Complete | 2026-03-24 |
| 5. Evidence-Grounded Completion | 0/2 | Not started | - |
