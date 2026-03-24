# Roadmap: Web Agent

## Overview

This roadmap turns the current placeholder deep-research path into a durable orchestrated workflow that can align tool contracts, run a resumable orchestration loop, persist plans and checkpoints, execute parallel research with existing retrieval tools, and only answer once evidence is normalized and sufficient.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Tool Contract Alignment** - Normalize retrieval tool names across quick, agentic, and deep-research modes.
- [ ] **Phase 2: Orchestrated Run Lifecycle** - Replace the placeholder deep-research entry flow with an orchestrator that can clarify and resume.
- [ ] **Phase 3: Persistent Planning Backbone** - Persist deep-research plans, workflow state, and inspectable progress artifacts.
- [ ] **Phase 4: Parallel Research Execution** - Fan out planned subquestions to research subagents that reuse existing retrieval behavior.
- [ ] **Phase 5: Evidence-Grounded Completion** - Normalize research evidence into AI messages and gate final answers on sufficient coverage.

## Phase Details

### Phase 1: Tool Contract Alignment
**Goal**: Users can rely on the same retrieval tool names in every runtime surface before deep-research orchestration builds on top of them.
**Depends on**: Nothing (first phase)
**Requirements**: TOOL-01, TOOL-02
**Success Criteria** (what must be TRUE):
  1. User can access the search tool as `web_search` in quick mode.
  2. User can access the search tool as `web_search` and the page-opening tool as `open_url` in agentic mode.
  3. User can access the search tool as `web_search` and the page-opening tool as `open_url` in deep-research mode.
**Plans**: TBD

Plans:
- [ ] 01-01: Audit current tool registrations and prompts across all three modes.
- [ ] 01-02: Rename or alias retrieval tools to the canonical public contract.
- [ ] 01-03: Verify the aligned names work end-to-end in each mode.

### Phase 2: Orchestrated Run Lifecycle
**Goal**: Users can start deep research through a dedicated orchestrator that asks for one clarification at a time and resumes the same run.
**Depends on**: Phase 1
**Requirements**: DEEP-01, DEEP-02, DEEP-03
**Success Criteria** (what must be TRUE):
  1. User can start a `deep_research` run and the run is handled by a deep-research orchestrator rather than the placeholder queued flow.
  2. User can receive no more than one clarifying question at a time before research begins.
  3. User can answer the clarifying question and continue the same `deep_research` run without losing prior context.
**Plans**: TBD

Plans:
- [ ] 02-01: Replace the current deep-research entry path with orchestrator-first control flow.
- [ ] 02-02: Add single-question clarification and resume handling for in-flight runs.

### Phase 3: Persistent Planning Backbone
**Goal**: Users can rely on deep-research runs to create durable plans, derive research threads from them, and survive interruption with inspectable progress.
**Depends on**: Phase 2
**Requirements**: PLAN-01, PLAN-02, PLAN-03, PLAN-04
**Success Criteria** (what must be TRUE):
  1. User can start a deep-research run and a persistent high-level research plan is created before research workers begin.
  2. User can have the orchestrator derive subquestions or research angles from the persisted plan.
  3. User can resume an interrupted deep-research run from filesystem artifacts plus LangGraph/Postgres-backed workflow state.
  4. User can inspect deep-research progress through persisted artifacts and logging without needing a new frontend surface.
**Plans**: TBD

Plans:
- [ ] 03-01: Persist plan artifacts and thread structure for each deep-research run.
- [ ] 03-02: Add checkpoint-backed resume behavior and progress logging.

### Phase 4: Parallel Research Execution
**Goal**: Users can have planned research threads executed in parallel by subagents that reuse the system's existing search and page-opening capabilities.
**Depends on**: Phase 3
**Requirements**: RSCH-01, RSCH-02
**Success Criteria** (what must be TRUE):
  1. User can have the orchestrator spawn parallel research subagents for the subquestions produced by the plan.
  2. User can have each research subagent use the same `web_search` and `open_url` retrieval behavior already supported by the project.
  3. User can observe parallel research progress in persisted logs or artifacts as subagents complete their work.
**Plans**: TBD

Plans:
- [ ] 04-01: Wire orchestrator delegation to parallel research workers.
- [ ] 04-02: Connect workers to existing retrieval tooling and execution policy.

### Phase 5: Evidence-Grounded Completion
**Goal**: Users receive a final deep-research answer only after the orchestrator has normalized citations from research workers and determined coverage is sufficient.
**Depends on**: Phase 4
**Requirements**: RSCH-03, RSCH-04, DEEP-04, TOOL-03
**Success Criteria** (what must be TRUE):
  1. User can have each research subagent return AI messages that include normalized search-result sources and crawl-result citations.
  2. User can have the orchestrator continue researching until it determines enough evidence exists to answer the original question deeply.
  3. User receives a final deep-research answer only after the orchestrator decides the planned subquestions have been answered well enough.
  4. User keeps the current top-level `deep_research` API response shape while evidence remains embedded in AI message content.
**Plans**: TBD

Plans:
- [ ] 05-01: Normalize worker outputs through citation-aware middleware.
- [ ] 05-02: Add coverage evaluation and final-answer gating in the orchestrator.

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Tool Contract Alignment | 0/3 | Not started | - |
| 2. Orchestrated Run Lifecycle | 0/2 | Not started | - |
| 3. Persistent Planning Backbone | 0/2 | Not started | - |
| 4. Parallel Research Execution | 0/2 | Not started | - |
| 5. Evidence-Grounded Completion | 0/2 | Not started | - |
