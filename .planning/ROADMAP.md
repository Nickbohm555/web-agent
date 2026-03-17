# Roadmap: Python LangGraph Web Agent Demo

## Overview

This roadmap delivers a local-first Python LangGraph agent flow that a user can run from a simple TypeScript UI while clearly inspecting search and crawl behavior. Phases are derived from v1 requirement boundaries: runtime foundation, tool capability, agent orchestration, frontend execution flow, and end-to-end observability. The sequence prioritizes early runnable infrastructure, then progressively completes the full prompt-to-answer workflow with transparent tool traces.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Local Runtime Foundation** - Boot the stack locally with environment-based provider configuration.
- [x] **Phase 2: Search and Crawl Tool Capability** - Make both backend tools callable and provider-backed.
- [ ] **Phase 3: Agent Execution Loop and API** - Expose iterative LangGraph execution through a backend endpoint.
- [ ] **Phase 4: Frontend Prompt Execution Surface** - Provide a minimal TypeScript UI that can run the agent and show tool activity status.
- [ ] **Phase 5: End-to-End Observability and Run History** - Complete full tool input/output visibility and correlated backend logs.

## Phase Details

### Phase 1: Local Runtime Foundation
**Goal**: Users can start and run the local stack with required API keys loaded from environment variables.
**Depends on**: Nothing (first phase)
**Requirements**: RUNTIME-01, RUNTIME-04
**Success Criteria** (what must be TRUE):
  1. User can start backend and frontend together using Docker Compose without manual service bootstrapping.
  2. Backend starts with `OPENAI_API_KEY` and `SERPER_API_KEY` loaded from environment variables and fails clearly when missing.
  3. User can confirm both services are reachable locally after stack startup.
**Plans**: 2 plans

Plans:
- [x] 01-01-define-docker-compose-services-and-shared-runtime-wiring-PLAN.md — Define Docker Compose services and shared runtime wiring
- [x] 01-02-implement-environment-configuration-loading-and-startup-validation-PLAN.md — Implement environment configuration loading and startup validation

### Phase 2: Search and Crawl Tool Capability
**Goal**: Agent runtime has working Python `web_search` and `web_crawl` tools that return usable results.
**Depends on**: Phase 1
**Requirements**: AGENT-02, AGENT-03
**Success Criteria** (what must be TRUE):
  1. Search tool can query Serper and return normalized links/snippets for agent use.
  2. Crawl tool can fetch a URL and return extracted content in a consistent response shape.
  3. Tool failures return explicit, debuggable errors rather than silent or empty failures.
**Plans**: 2 plans

Plans:
- [x] 02-01-implement-serper-backed-web-search-tool-in-python-PLAN.md — Implement Serper-backed `web_search` tool in Python
- [x] 02-02-implement-in-house-python-web-crawl-extraction-flow-PLAN.md — Implement in-house Python `web_crawl` extraction flow

### Phase 3: Agent Execution Loop and API
**Goal**: User prompts are executed by a ReAct-style LangGraph agent that iterates through tools before answering.
**Depends on**: Phase 2
**Requirements**: AGENT-01, AGENT-04, RUNTIME-03
**Success Criteria** (what must be TRUE):
  1. Frontend-callable backend endpoint accepts a prompt and triggers one LangGraph agent run.
  2. Agent can call one or more tools in sequence and stop when enough context is gathered.
  3. User receives a final agent-generated answer from the same run request.
  4. API response model is stable enough for frontend rendering of final answer plus run metadata.
**Plans**: TBD

Plans:
- [ ] 03-01: Wire LangGraph ReAct loop with tool binding
- [ ] 03-02: Expose backend execution endpoint and response contract

### Phase 4: Frontend Prompt Execution Surface
**Goal**: Users can run prompts from a minimal TypeScript UI and track tool-call progress.
**Depends on**: Phase 3
**Requirements**: RUNTIME-02, OBS-01
**Success Criteria** (what must be TRUE):
  1. User can enter a prompt and start a run from one simple frontend interface.
  2. Frontend successfully calls backend execution API and displays run state transitions.
  3. User can see each tool call with status and duration as the run progresses.
**Plans**: 3 plans

Plans:
- [ ] 04-01: Build minimal prompt/run UI and API client wiring
- [ ] 04-02: Add SSE event contracts + reducer-safe run state handling
- [ ] 04-03: Render per-tool status and duration in run timeline

### Phase 5: End-to-End Observability and Run History
**Goal**: User can inspect full tool I/O, backend event logs, and final-answer history in one debugging flow.
**Depends on**: Phase 4
**Requirements**: OBS-02, OBS-03, OBS-04
**Success Criteria** (what must be TRUE):
  1. User can inspect complete input and output payloads for each tool call in the frontend.
  2. User can inspect structured backend logs for agent and tool events via Docker logs.
  3. User can review the final answer and full per-run tool history in one cohesive UI flow.
  4. Tool events shown in UI can be correlated with backend logs for the same run.
**Plans**: TBD

Plans:
- [ ] 05-01: Add full tool payload rendering in UI
- [ ] 05-02: Emit and correlate structured backend observability logs
- [ ] 05-03: Finalize run history presentation with answer + tool trace

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Local Runtime Foundation | 2/2 | Completed | 2026-03-17 |
| 2. Search and Crawl Tool Capability | 2/2 | Completed | 2026-03-17 |
| 3. Agent Execution Loop and API | 0/2 | Not started | - |
| 4. Frontend Prompt Execution Surface | 0/3 | Not started | - |
| 5. End-to-End Observability and Run History | 0/3 | Not started | - |
