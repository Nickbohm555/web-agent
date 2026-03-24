# Requirements: Web Agent

**Defined:** 2026-03-24
**Core Value:** Deep research must be able to break a complex question into the right research threads, gather enough evidence across those threads, and return a deeply supported answer only when the orchestrator has enough coverage to do so confidently.

## v1 Requirements

### Deep Research Orchestration

- [ ] **DEEP-01**: User can start a `deep_research` run that is executed by an orchestrator agent dedicated to deep research.
- [ ] **DEEP-02**: User can receive at most one clarifying question at a time when the orchestrator determines more context is needed before research starts.
- [ ] **DEEP-03**: User can resume the same `deep_research` run after answering a clarifying question instead of starting over.
- [ ] **DEEP-04**: User can receive a final deep-research answer only after the orchestrator determines the planned subquestions have been answered well enough.

### Planning And Persistence

- [ ] **PLAN-01**: User can have each `deep_research` run create a persistent high-level research plan before parallel research begins.
- [ ] **PLAN-02**: User can have the orchestrator derive subquestions or research angles from that persistent plan.
- [ ] **PLAN-03**: User can resume an interrupted `deep_research` run from persisted workflow state backed by LangGraph checkpointing and Postgres.
- [ ] **PLAN-04**: User can inspect deep-research progress indirectly through persisted artifacts and logging without requiring a new frontend feature set.

### Research Subagents

- [ ] **RSCH-01**: User can have the orchestrator spawn parallel research subagents for subquestions generated from the plan.
- [ ] **RSCH-02**: User can have each research subagent use the same retrieval capabilities the project already exposes for web search and URL opening.
- [ ] **RSCH-03**: User can have each research subagent return an AI message that includes normalized search-result sources and crawl-result citations for the orchestrator to use.
- [ ] **RSCH-04**: User can have the orchestrator loop on research results until it decides enough evidence exists to answer the original question deeply.

### Tool Contracts

- [ ] **TOOL-01**: User can access the search tool as `web_search` in quick, agentic, and deep-research modes.
- [ ] **TOOL-02**: User can access the page-opening or crawl tool as `open_url` in quick, agentic, and deep-research modes.
- [ ] **TOOL-03**: User can keep the current top-level API response shape for `deep_research` runs while evidence is carried inside AI message content via middleware.

## v2 Requirements

### Deep Research Experience

- **OBS-01**: User can inspect deep-research plans, subagent outputs, and synthesis state in a dedicated frontend view.
- **PLAN-05**: User can edit or approve the generated high-level research plan before subagent execution begins.
- **RSCH-05**: User can control research breadth and depth knobs per run.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Reworking quick-mode execution flow | Not part of this deep-research initiative |
| Reworking agentic-mode execution flow | Not part of this deep-research initiative |
| Redesigning the deep-research API envelope | Current response shape should remain stable |
| Broad frontend redesign for deep research | Backend orchestration is the current priority |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| DEEP-01 | Phase TBD | Pending |
| DEEP-02 | Phase TBD | Pending |
| DEEP-03 | Phase TBD | Pending |
| DEEP-04 | Phase TBD | Pending |
| PLAN-01 | Phase TBD | Pending |
| PLAN-02 | Phase TBD | Pending |
| PLAN-03 | Phase TBD | Pending |
| PLAN-04 | Phase TBD | Pending |
| RSCH-01 | Phase TBD | Pending |
| RSCH-02 | Phase TBD | Pending |
| RSCH-03 | Phase TBD | Pending |
| RSCH-04 | Phase TBD | Pending |
| TOOL-01 | Phase TBD | Pending |
| TOOL-02 | Phase TBD | Pending |
| TOOL-03 | Phase TBD | Pending |

**Coverage:**
- v1 requirements: 15 total
- Mapped to phases: 0
- Unmapped: 15 ⚠️

---
*Requirements defined: 2026-03-24*
*Last updated: 2026-03-24 after initial definition*
