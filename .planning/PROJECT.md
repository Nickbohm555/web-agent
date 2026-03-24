# Web Agent

## What This Is

Web Agent is a dual-surface retrieval system with a TypeScript frontend/runtime layer and a Python backend agent runtime for search, crawl, and answer generation. The current product already supports quick, agentic, and deep-research execution modes, and this project focuses on turning deep research into a true orchestrated multi-agent workflow with persistent planning and resumable clarification.

## Core Value

Deep research must be able to break a complex question into the right research threads, gather enough evidence across those threads, and return a deeply supported answer only when the orchestrator has enough coverage to do so confidently.

## Requirements

### Validated

- ✓ Local frontend and backend services can run together for retrieval and agent execution — existing
- ✓ Users can submit prompts through quick, agentic, and deep-research modes — existing
- ✓ Backend web retrieval already supports typed search and crawl tool flows with policy enforcement — existing
- ✓ Frontend run history and streaming infrastructure already capture backend run events — existing

### Active

- [ ] Deep-research mode uses an orchestrator-driven Deep Agents workflow instead of the current queued placeholder flow
- [ ] Deep-research runs can pause to ask a single clarifying question and resume after the user answers
- [ ] Deep-research planning artifacts and checkpoints persist through filesystem-backed planning plus LangGraph/Postgres state
- [ ] Deep-research research subagents execute parallel subquestions using the existing web retrieval behavior
- [ ] Research subagent responses are normalized through middleware so AI messages carry search-result sources and crawl-result citations
- [ ] Tool naming is aligned across quick, agentic, and deep-research modes so the crawl/open-page tool is exposed as `open_url` and search remains `web_search`

### Out of Scope

- Changing the core execution behavior of quick mode — only tool naming alignment is included
- Changing the core execution behavior of agentic mode — only tool naming alignment is included
- Frontend feature work for deep-research orchestration beyond using existing logging or current views to inspect the plan — backend workflow is the priority
- Redesigning the existing deep-research API response shape — the current shape stays in place

## Context

The repository is a brownfield system with two parallel surfaces: an Express frontend/server in `src/frontend/` and a FastAPI/LangChain backend in `backend/`. The current deep-research path exists, but the backend codebase map shows it is still largely an in-memory queued flow rather than a full orchestrated deep-agent system. Existing backend retrieval tools already provide the right substrate for research workers, so this project should reuse those retrieval behaviors instead of creating a new crawl/search stack.

The current frontend already has run-history and event plumbing, which makes it possible to surface deep-research progress later without first redesigning the UI. The immediate need is a backend-first orchestration flow that can classify whether clarification is needed, persist a high-level plan, fan out research work in parallel, and decide when enough evidence has been gathered to answer the original question deeply.

## Constraints

- **Architecture**: Keep deep-research orchestration isolated to the deep-research backend path — quick and agentic should not be structurally rewritten as part of this work
- **Persistence**: Use persistent artifacts and LangGraph/Postgres checkpointing for deep-research state — in-memory only state is insufficient
- **Observability**: Planning and research progress must remain inspectable through logging or existing frontend views — internal state cannot become opaque
- **Tool Contracts**: Retrieval tool naming must be explicit and user-facing — `web_search` and `open_url` should reflect real runtime behavior
- **Code Organization**: Backend orchestration should stay split into focused modules rather than expanding monolithic runtime files — this repo already has explicit guidance to keep runtime code atomic

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Deep-research will use an orchestrator-first Deep Agents workflow | The current queued flow does not satisfy the need for planning, delegation, and stop-when-enough coverage | — Pending |
| Clarification happens as a single question at a time | Keeps the user interaction loop simple and matches the desired resume flow | — Pending |
| Planning artifacts persist internally with filesystem-backed storage plus checkpointing | Deep research needs resumability, inspectability, and durable run state | — Pending |
| Final sources and citations stay inside AI message content via middleware rather than becoming new top-level response fields | Preserves the existing API shape while still making evidence available to the orchestrator and final answer | — Pending |
| Tool naming is normalized across all three execution modes | Consistent tool names reduce prompt/tool drift and keep runtime behavior understandable | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition**:
1. Requirements invalidated? -> Move to Out of Scope with reason
2. Requirements validated? -> Move to Validated with phase reference
3. New requirements emerged? -> Add to Active
4. Decisions to log? -> Add to Key Decisions
5. "What This Is" still accurate? -> Update if drifted

**After each milestone**:
1. Full review of all sections
2. Core Value check -> still the right priority?
3. Audit Out of Scope -> reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-03-24 after initialization*
