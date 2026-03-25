# Runtime Retest Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make quick, agentic, and deep-research pages work end to end with solid responses, real agentic conversation persistence, and real deep-research synthesis/clarification behavior.

**Architecture:** Pass explicit `thread_id` values through the frontend and backend contracts, bind agentic runs to a Postgres checkpointer-backed runtime, and upgrade deep research from placeholder completion into a clarification-aware background workflow that synthesizes the subagent artifacts it collected. Keep the existing split between frontend routes, backend API services, runtime modules, and persistence helpers.

**Tech Stack:** Express frontend, FastAPI backend, LangGraph/LangChain agents, Deep Agents, Postgres store/checkpointer, Vitest/Pytest

---

### Task 1: Thread-Aware Run Contracts

**Files:**
- Modify: `src/frontend/contracts.ts`
- Modify: `src/frontend/client/api-client.ts`
- Modify: `src/frontend/client/app.ts`
- Modify: `src/frontend/routes/runs.ts`
- Modify: `backend/api/schemas/agent_run.py`
- Modify: `backend/api/services/agent_run.py`
- Test: `src/tests/frontend-api/backend-agent.test.ts`
- Test: `backend/tests/api/test_agent_run_route.py`

- [ ] Add failing tests for optional `thread_id` passthrough.
- [ ] Run the targeted tests and confirm they fail for missing thread propagation.
- [ ] Implement the minimal request/response wiring.
- [ ] Re-run the targeted tests and confirm they pass.

### Task 2: Agentic Checkpointer Runtime

**Files:**
- Create: `backend/agent/persistence/checkpointer.py`
- Modify: `backend/agent/runtime_execution.py`
- Modify: `backend/agent/runtime.py`
- Test: `backend/tests/agent/test_runtime.py`

- [ ] Add failing tests showing agentic runs do not supply `thread_id` into a checkpoint-backed invocation path.
- [ ] Run the targeted runtime tests and confirm the failure.
- [ ] Implement a focused Postgres checkpointer helper and use it for agentic runtime invocation.
- [ ] Re-run the targeted runtime tests and confirm they pass.

### Task 3: Deep Research Clarification + Real Final Answer

**Files:**
- Modify: `backend/agent/schemas/deep_research.py`
- Modify: `backend/agent/deep_research_runtime.py`
- Modify: `backend/agent/deep_research_verification.py`
- Modify: `backend/api/schemas/deep_research_status.py`
- Modify: `src/frontend/contracts.ts`
- Test: `backend/tests/agent/test_deep_research_runtime.py`

- [ ] Add failing tests for clarification-needed deep-research requests and placeholder final synthesis.
- [ ] Run the targeted deep-research tests and confirm the failure.
- [ ] Implement minimal clarification gating plus synthesis from research artifacts/sources.
- [ ] Re-run the targeted deep-research tests and confirm they pass.

### Task 4: End-to-End Verification

**Files:**
- Test only

- [ ] Run backend targeted pytest coverage for the changed areas.
- [ ] Run frontend targeted vitest coverage for the changed areas.
- [ ] Refresh the affected Docker containers.
- [ ] Run live quick, agentic, and deep-research flows and record the observed runtime behavior.
