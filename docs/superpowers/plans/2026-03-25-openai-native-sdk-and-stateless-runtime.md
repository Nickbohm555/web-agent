# OpenAI-Native SDK And Stateless Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Python SDK’s host-based client API with an OpenAI-native `api_key + model + query` interface and remove backend database-backed memory so agent runs are single-pass only.

**Architecture:** The SDK will call the official OpenAI Python client directly using the Responses API and the built-in web search tool, exposing only `quick_search(query)` and `agentic_search(query)` on a client configured with `api_key` and `model`. The backend will be simplified to stateless one-shot execution by removing the Postgres checkpointer requirement, dropping `thread_id` from the public run contract, and removing startup/database configuration that only existed for memory-backed agent runs.

**Tech Stack:** Python, OpenAI Python SDK, Pydantic, FastAPI, pytest, docker compose

---

### Task 1: Lock The Stateless Backend Contract

**Files:**
- Modify: `backend/tests/api/test_agent_run_route.py`
- Modify: `backend/tests/api/test_agent_run_service.py`
- Modify: `backend/tests/test_startup_settings.py`
- Modify: `backend/api/schemas/agent_run.py`
- Modify: `backend/api/services/agent_run.py`
- Modify: `backend/agent/runtime_execution.py`
- Modify: `backend/agent/runtime_policy.py`
- Modify: `backend/app/config.py`
- Modify: `backend/main.py`
- Modify: `backend/requirements.txt`
- Modify: `docker-compose.yml`

- [ ] **Step 1: Write the failing tests**

```python
def test_run_request_contract_omits_thread_id():
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./.venv/bin/python -m pytest backend/tests/api/test_agent_run_service.py backend/tests/api/test_agent_run_route.py backend/tests/test_startup_settings.py -v`
Expected: FAIL because the API still accepts `thread_id` and startup still requires the database URL.

- [ ] **Step 3: Write minimal implementation**

```python
class AgentRunRequest(BaseModel):
    prompt: str
    mode: AgentRunMode
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./.venv/bin/python -m pytest backend/tests/api/test_agent_run_service.py backend/tests/api/test_agent_run_route.py backend/tests/test_startup_settings.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tests/api/test_agent_run_service.py backend/tests/api/test_agent_run_route.py backend/tests/test_startup_settings.py backend/api/schemas/agent_run.py backend/api/services/agent_run.py backend/agent/runtime_execution.py backend/agent/runtime_policy.py backend/app/config.py backend/main.py backend/requirements.txt docker-compose.yml
git commit -m "refactor: make agent runtime stateless"
```

### Task 2: Replace The Python SDK With An OpenAI-Native Client

**Files:**
- Modify: `sdk/python/tests/test_client.py`
- Modify: `sdk/python/src/web_agent_sdk/client.py`
- Modify: `sdk/python/src/web_agent_sdk/__init__.py`
- Modify: `sdk/python/src/web_agent_sdk/schemas/agentic_search.py`
- Modify: `sdk/python/src/web_agent_sdk/schemas/quick_search.py`
- Modify: `sdk/python/src/web_agent_sdk/errors.py`
- Modify: `sdk/python/pyproject.toml`

- [ ] **Step 1: Write the failing tests**

```python
def test_client_uses_openai_responses_api_with_model_and_query():
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd sdk/python && ../../.venv/bin/python -m pytest tests/test_client.py -v`
Expected: FAIL because the SDK still expects `base_url` and `backend_base_url`.

- [ ] **Step 3: Write minimal implementation**

```python
class WebAgentClient:
    def __init__(self, *, api_key: str, model: str):
        ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd sdk/python && ../../.venv/bin/python -m pytest tests/test_client.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add sdk/python/tests/test_client.py sdk/python/src/web_agent_sdk/client.py sdk/python/src/web_agent_sdk/__init__.py sdk/python/src/web_agent_sdk/schemas/agentic_search.py sdk/python/src/web_agent_sdk/schemas/quick_search.py sdk/python/src/web_agent_sdk/errors.py sdk/python/pyproject.toml
git commit -m "feat: make python sdk openai-native"
```

### Task 3: Rewrite Documentation And Publish A New SDK Version

**Files:**
- Modify: `sdk/python/README.md`
- Modify: `README.md`

- [ ] **Step 1: Write the failing test**

No new code test. This task is doc and package verification.

- [ ] **Step 2: Verify package builds**

Run: `cd sdk/python && ../../.venv/bin/python -m build`
Expected: build succeeds for the new version.

Run: `cd sdk/python && ../../.venv/bin/python -m twine check dist/*`
Expected: PASS

- [ ] **Step 3: Rewrite docs for the new API**

Document usage as:

```python
client = WebAgentClient(api_key="...", model="gpt-5")
quick = client.quick_search("Find pricing")
agentic = client.agentic_search("Investigate this company")
```

- [ ] **Step 4: Publish and refresh runtime**

Run: `docker compose up -d --build backend`
Expected: backend starts without a Postgres dependency.

Run: `cd sdk/python && TWINE_USERNAME=__token__ TWINE_PASSWORD=... ../../.venv/bin/python -m twine upload dist/*`
Expected: new PyPI version published.

- [ ] **Step 5: Commit**

```bash
git add sdk/python/README.md README.md
git commit -m "docs: update sdk usage for openai-native client"
```
