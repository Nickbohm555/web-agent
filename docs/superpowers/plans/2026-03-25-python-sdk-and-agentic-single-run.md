# Python SDK And Agentic Single-Run Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a publishable Python SDK with `quick_search` and `agentic_search` methods, backed by stable single-run HTTP APIs.

**Architecture:** Keep the SDK as a small hand-written HTTP client package under `sdk/python/`, with explicit Pydantic request and response models in a dedicated `schemas/` package. Extend the existing backend `/api/agent/run` surface so `mode="agentic"` executes synchronously through the already-wired runtime rather than being rejected.

**Tech Stack:** Python, FastAPI, Pydantic, `httpx`, pytest

---

### Task 1: Capture Backend Single-Run Agentic Contract

**Files:**
- Modify: `backend/tests/api/test_agent_run_service.py`
- Modify: `backend/tests/api/test_agent_run_route.py`
- Modify: `backend/api/services/agent_run.py`

- [ ] **Step 1: Write the failing test**

```python
def test_execute_agent_run_request_returns_sync_success_for_agentic_mode(...):
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest backend/tests/api/test_agent_run_service.py -k agentic -v`
Expected: FAIL because `agentic` is still rejected as unsupported.

- [ ] **Step 3: Write minimal implementation**

```python
if payload.mode == "deep_research":
    ...
result = run_agent_once(payload.prompt, payload.mode, thread_id=payload.thread_id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest backend/tests/api/test_agent_run_service.py backend/tests/api/test_agent_run_route.py -k agentic -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tests/api/test_agent_run_service.py backend/tests/api/test_agent_run_route.py backend/api/services/agent_run.py
git commit -m "feat: allow agentic single-run api execution"
```

### Task 2: Add Python SDK Package And Contracts

**Files:**
- Create: `sdk/python/pyproject.toml`
- Create: `sdk/python/README.md`
- Create: `sdk/python/src/web_agent_sdk/__init__.py`
- Create: `sdk/python/src/web_agent_sdk/client.py`
- Create: `sdk/python/src/web_agent_sdk/errors.py`
- Create: `sdk/python/src/web_agent_sdk/schemas/__init__.py`
- Create: `sdk/python/src/web_agent_sdk/schemas/agentic_search.py`
- Create: `sdk/python/src/web_agent_sdk/schemas/quick_search.py`
- Create: `sdk/python/tests/test_client.py`

- [ ] **Step 1: Write the failing test**

```python
def test_quick_search_posts_quick_mode(...):
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd sdk/python && pytest tests/test_client.py -v`
Expected: FAIL because the package and client do not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
class WebAgentClient:
    def quick_search(self, prompt: str) -> QuickSearchResponse: ...
    def agentic_search(self, prompt: str) -> AgenticSearchResponse: ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd sdk/python && pytest tests/test_client.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add sdk/python
git commit -m "feat: add python sdk for quick and agentic search"
```

### Task 3: Verify Integration And Operational Follow-Through

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Write the failing test**

No new failing test. This task is verification and documentation only.

- [ ] **Step 2: Run focused verification**

Run: `pytest backend/tests/api/test_agent_run_service.py backend/tests/api/test_agent_run_route.py -v`
Expected: PASS

Run: `cd sdk/python && pytest tests/test_client.py -v`
Expected: PASS

- [ ] **Step 3: Update minimal docs**

Document the Python SDK location and the two public methods in `README.md`.

- [ ] **Step 4: Refresh runtime**

Run: `docker compose up -d --build backend`
Expected: backend container rebuilt or refreshed with the API change.

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: document python sdk entrypoints"
```
