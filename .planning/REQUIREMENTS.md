# Requirements: Python LangGraph Web Agent Demo

**Defined:** 2026-03-17
**Core Value:** A user can run one prompt from a simple UI and clearly see how the agent invokes search and crawl tools end-to-end.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Agent Execution

- [ ] **AGENT-01**: User can submit a prompt and receive an agent-generated final response.
- [ ] **AGENT-02**: Agent can call a Serper-backed web search tool to retrieve relevant links/snippets.
- [ ] **AGENT-03**: Agent can call an in-house Python web crawl tool to fetch and extract page content.
- [ ] **AGENT-04**: Agent can iteratively call tools until it decides it has enough context to answer.

### Observability

- [ ] **OBS-01**: User can see each tool call in the frontend with status and duration.
- [ ] **OBS-02**: User can inspect full tool inputs and outputs for each call in the frontend.
- [ ] **OBS-03**: User can inspect structured backend logs for agent/tool events via Docker logs.
- [ ] **OBS-04**: User can review final answer and per-run tool history in one UI flow.

### Local Runtime + UI

- [ ] **RUNTIME-01**: User can start backend + frontend stack locally with Docker Compose.
- [ ] **RUNTIME-02**: User can use a TypeScript frontend with a single input/run interface for agent execution.
- [ ] **RUNTIME-03**: Frontend can invoke backend API endpoint to execute the LangGraph agent.
- [ ] **RUNTIME-04**: Backend reads `OPENAI_API_KEY` and `SERPER_API_KEY` from environment variables at runtime.

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Crawler Hardening

- **CRAWL-01**: Crawler supports selective browser fallback for JS-heavy pages.
- **CRAWL-02**: Crawler enforces stronger robots/politeness/compliance guardrails.

### Developer Experience

- **DX-01**: UI includes richer multi-run trace analysis (filters, search, export).
- **DX-02**: Backend includes expanded reliability controls (retry policies per tool class).

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Authentication and user accounts | Explicitly excluded to keep v1 focused and simple |
| Multi-agent architecture | v1 requires one simple agent with two tools only |
| Production deployment/infrastructure hardening | Local Docker Compose is sufficient for current validation goal |
| Full parity migration of all legacy TypeScript internals | Immediate focus is runnable Python agent path with observability |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| AGENT-01 | Phase 3 | Pending |
| AGENT-02 | Phase 2 | Pending |
| AGENT-03 | Phase 2 | Pending |
| AGENT-04 | Phase 3 | Pending |
| OBS-01 | Phase 4 | Pending |
| OBS-02 | Phase 5 | Pending |
| OBS-03 | Phase 5 | Pending |
| OBS-04 | Phase 5 | Pending |
| RUNTIME-01 | Phase 1 | Pending |
| RUNTIME-02 | Phase 4 | Pending |
| RUNTIME-03 | Phase 3 | Pending |
| RUNTIME-04 | Phase 1 | Pending |

**Coverage:**
- v1 requirements: 12 total
- Mapped to phases: 12
- Unmapped: 0

---
*Requirements defined: 2026-03-17*
*Last updated: 2026-03-17 after roadmap mapping*
