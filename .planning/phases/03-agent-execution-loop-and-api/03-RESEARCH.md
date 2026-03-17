# Phase 03: Agent Execution Loop and API - Research

**Researched:** 2026-03-17  
**Domain:** LangGraph/LangChain ReAct execution loop + FastAPI request/response contract  
**Confidence:** HIGH

## Summary

Phase 03 should implement a single synchronous HTTP run endpoint that executes one LangGraph-backed ReAct loop with exactly two tools (`web_search`, `web_crawl`) and returns a stable response model containing final answer plus run metadata. Current LangChain agent docs show `create_agent(...)` as the production-ready path built on LangGraph runtime semantics, including tool loops until a stop condition or iteration limit.

FastAPI + Pydantic are the standard API contract stack for this phase: request validation, stable typed response filtering (`response_model`), and explicit failure surfaces (`HTTPException`). For this phase's scope, keep execution in-process per request (no queue, no background worker) and cap loop depth with LangGraph recursion limits to avoid non-terminating tool cycles.

Primary architecture seam: separate `agent_runtime` (LangGraph execution concerns) from `api_contract` (request/response + error model) so frontend can rely on a stable payload even if agent internals evolve in later phases.

**Primary recommendation:** Use a single FastAPI `POST /api/agent/run` endpoint that calls one LangGraph-based agent instance (`create_agent` + two tools), enforces loop bounds (`recursion_limit`), and returns a versioned Pydantic response contract.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `langgraph` | `1.1.2` | Stateful agent orchestration runtime | Official LangGraph runtime for durable graph-based loops; direct support for step-bounded execution |
| `langchain` | `1.2.12` | Agent factory and tool loop abstractions | `create_agent` is documented as production-ready and built on LangGraph |
| `langchain-openai` | `1.1.11` | OpenAI chat model integration | Standard OpenAI provider package for LangChain tool-calling agents |
| `fastapi` | `0.135.1` | Backend endpoint layer | Strong request validation + OpenAPI + response-model filtering |
| `pydantic` | `2.12.5` | Contract models for request/response | Explicit schema validation and controlled serialization via `model_dump()` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `uvicorn` | `0.42.0` | ASGI server runtime | Local Docker service start and API serving |
| `typing-extensions` | latest | `TypedDict` support for agent state | Needed when defining explicit custom state shape |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `langchain.create_agent` on LangGraph | Hand-built `StateGraph` loop | More control, but more custom orchestration code and higher bug surface in Phase 03 |
| Synchronous run endpoint | Async run queue + polling API | Better for long runs, but unnecessary complexity before observability/history phases |
| FastAPI response model | Unstructured `dict` passthrough | Faster to prototype, but unstable for frontend contract and harder to evolve safely |

**Installation:**
```bash
pip install -U langgraph langchain langchain-openai fastapi pydantic uvicorn
```

## Architecture Patterns

### Recommended Project Structure
```
backend/
├── api/
│   ├── routes/agent_run.py      # POST /api/agent/run endpoint
│   ├── contracts.py             # Pydantic request/response models
│   └── errors.py                # HTTP error mapping
├── agent/
│   ├── runtime.py               # create_agent/init + run wrapper
│   ├── prompts.py               # system prompt and tool usage rules
│   └── state.py                 # optional TypedDict state extensions
├── tools/
│   ├── web_search.py            # Phase 2 tool adapter
│   └── web_crawl.py             # Phase 2 tool adapter
└── main.py                      # FastAPI app + lifespan wiring
```

### Pattern 1: Single-run Agent Runtime Facade
**What:** A narrow function (e.g., `run_agent_once(prompt) -> AgentRunResult`) that hides LangGraph/LangChain internals from API routes.  
**When to use:** Always; route handlers should not manage tool loops directly.  
**Example:**
```python
# Source: https://docs.langchain.com/oss/python/langchain/agents
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

model = ChatOpenAI(model="gpt-4.1-mini", temperature=0)
agent = create_agent(model=model, tools=[web_search, web_crawl])

def run_agent_once(prompt: str):
    return agent.invoke(
        {"messages": [{"role": "user", "content": prompt}]},
        {"recursion_limit": 12},
    )
```

### Pattern 2: Contract-first API Boundary
**What:** Pydantic models define request/response; FastAPI `response_model` enforces outbound payload shape.  
**When to use:** All external frontend-callable endpoints.  
**Example:**
```python
# Source: https://fastapi.tiangolo.com/tutorial/response-model/
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

class RunRequest(BaseModel):
    prompt: str

class RunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: str
    status: str
    final_answer: str
    tool_call_count: int

router = APIRouter()

@router.post("/api/agent/run", response_model=RunResponse)
async def run_agent(req: RunRequest) -> RunResponse:
    result = run_agent_once(req.prompt)
    return RunResponse(**result)
```

### Pattern 3: App Lifespan Initialization for Shared Agent Instance
**What:** Initialize model/agent once at startup using FastAPI lifespan; reuse per request.  
**When to use:** Default for local runtime; avoids reinitializing provider clients every call.  
**Example:**
```python
# Source: https://fastapi.tiangolo.com/advanced/events/
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.agent = build_agent()  # create_agent(...)
    yield
    app.state.agent = None

app = FastAPI(lifespan=lifespan)
```

### Architecture Seams and Contracts (planner-critical)
- **Seam: `tools` -> `agent runtime`**: tool interfaces from Phase 2 must be callable LangChain tools with stable names exactly `web_search` and `web_crawl`.
- **Seam: `agent runtime` -> `API`**: runtime returns normalized `AgentRunResult` (`final_answer`, step counts, tool history summary, timing).
- **Seam: `API` -> `frontend`**: response contract versioned and additive-only; required keys stay stable once Phase 03 ships.
- **Seam: `config/env` -> `runtime`**: startup fails fast if required keys missing (depends on Phase 1 key validation).

### Anti-Patterns to Avoid
- **Route-level agent orchestration:** running loop logic directly in route handler couples transport and runtime.
- **Unbounded loops:** no `recursion_limit` or stopping guard risks hangs/timeouts.
- **Leaky tool payload contract:** exposing raw provider internals breaks frontend stability.
- **Changing response keys ad hoc:** breaks frontend rendering and Phase 4 integration velocity.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| ReAct control loop | Custom while-loop parser for tool calls | LangGraph/LangChain agent runtime (`create_agent`) | Already handles model/tool turn management and stop conditions |
| HTTP schema filtering | Manual `dict` sanitation | FastAPI `response_model` + Pydantic models | Built-in validation/filtering and OpenAPI alignment |
| Tool JSON schema generation | Manual JSON schema assembly | `@tool` metadata + typed signatures | Better model tool-selection reliability and lower mismatch risk |
| Loop runaway protection | Ad hoc counters in multiple places | LangGraph `recursion_limit` invoke config (+ optional local counter) | Canonical runtime guard against infinite cycles |

**Key insight:** Phase 03 succeeds by composing mature orchestration and API-contract primitives; custom loop/framework plumbing is where regressions and schedule risk concentrate.

## Common Pitfalls

### Pitfall 1: Non-terminating tool loop
**What goes wrong:** Agent keeps alternating tool/model steps and never emits final answer.  
**Why it happens:** Weak system instructions + missing recursion cap.  
**How to avoid:** Set `recursion_limit` per run and include explicit "stop when enough context" instruction.  
**Warning signs:** Runs frequently exceed expected step count, timeout spikes, repeated identical tool calls.

### Pitfall 2: Unstable frontend payload
**What goes wrong:** Frontend breaks when backend fields drift between runs/commits.  
**Why it happens:** Returning raw runtime structures instead of schema-governed response model.  
**How to avoid:** Versioned Pydantic response contract; forbid extras on core envelope.  
**Warning signs:** Frontend conditional parsing, frequent undefined/null checks for top-level fields.

### Pitfall 3: Tool identity mismatch with Phase 2
**What goes wrong:** Agent emits tool names not wired in runtime (`web_search` vs `search_web`, etc.).  
**Why it happens:** Renamed decorator names or mismatch between prompt/tool registry.  
**How to avoid:** Enforce canonical tool names in decorators and startup assertion against expected set.  
**Warning signs:** "Tool not found" runtime errors despite tool code existing.

### Pitfall 4: Error surface hides root cause
**What goes wrong:** API returns generic 500 with no actionable context for frontend or local debugging.  
**Why it happens:** Unmapped exceptions and no contract-level error envelope.  
**How to avoid:** Map expected failure modes (validation, tool failure, recursion limit) to explicit HTTP + error codes.  
**Warning signs:** Repeated opaque failures requiring log spelunking.

## Code Examples

Verified patterns from official sources:

### Tool Loop Stop Condition in LangGraph
```python
# Source: https://docs.langchain.com/oss/python/langgraph/quickstart
def should_continue(state):
    last_message = state["messages"][-1]
    if last_message.tool_calls:
        return "tool_node"
    return END
```

### Agent Invocation with Input Messages
```python
# Source: https://docs.langchain.com/oss/python/langchain/agents
result = agent.invoke({
    "messages": [{"role": "user", "content": "Find sources then answer briefly"}]
})
```

### Recursion Guard on Invoke
```python
# Source: https://docs.langchain.com/oss/python/langgraph/errors/GRAPH_RECURSION_LIMIT
result = graph.invoke(inputs, {"recursion_limit": 100})
```

### FastAPI Contract Enforcement
```python
# Source: https://fastapi.tiangolo.com/tutorial/response-model/
@app.post("/run", response_model=RunResponse)
async def run(req: RunRequest):
    return run_agent_once(req.prompt)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual agent executors with custom loop glue | `create_agent` documented as production-ready and graph-backed | LangChain v1 era docs | Faster reliable implementation with less orchestration boilerplate |
| Ad hoc dict contracts for API payloads | Pydantic v2 model-driven contracts + FastAPI response filtering | FastAPI/Pydantic v2 mainstream | Stable frontend integration and safer refactors |

**Deprecated/outdated:**
- `startup`/`shutdown` event pair as primary init strategy: FastAPI docs recommend lifespan for startup/shutdown lifecycle management.

## Verification Strategy (for PLAN task decomposition)

### Contract verification
- POST endpoint rejects invalid request body with schema errors.
- Success response always includes required envelope: `run_id`, `status`, `final_answer`, metadata object.
- Response keys/types remain constant across runs with/without tool usage.

### Agent behavior verification
- Prompt requiring no tool use returns direct final answer in one run.
- Prompt requiring both tools shows sequential tool use before final answer.
- Loop stop occurs before recursion cap for normal prompts.
- Forced loop case triggers bounded failure with explicit error mapping.

### Integration seam verification
- Startup fails clearly when agent/tools not wired or env keys unavailable.
- Runtime rejects missing expected tool names (`web_search`, `web_crawl`) at boot.
- Frontend can render final answer + metadata from one synchronous response.

## Open Questions

1. **Final response metadata granularity for Phase 03**
   - What we know: success criteria require metadata stable enough for frontend rendering.
   - What's unclear: exact minimum metadata fields expected before Phase 4/5 observability work.
   - Recommendation: lock a minimal envelope now (`run_id`, `status`, `final_answer`, `tool_call_count`, `elapsed_ms`) and only add optional fields later.

2. **Execution timeout policy for long prompts/tool chains**
   - What we know: recursion limit can bound steps, but wall-clock timeout policy is not defined in roadmap text.
   - What's unclear: whether timeout should be API-layer, model-layer, or both.
   - Recommendation: set conservative API request timeout and include timeout error code in response model.

## Sources

### Primary (HIGH confidence)
- [LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview) - positioning and install guidance
- [LangGraph quickstart](https://docs.langchain.com/oss/python/langgraph/quickstart) - graph loop pattern, tool-call routing
- [LangGraph recursion error docs](https://docs.langchain.com/oss/python/langgraph/errors/GRAPH_RECURSION_LIMIT) - `recursion_limit` runtime guard
- [LangChain agents docs](https://docs.langchain.com/oss/python/langchain/agents) - `create_agent`, loop behavior, streaming/progress semantics
- [LangChain tools docs](https://docs.langchain.com/oss/python/langchain/tools) - tool declaration patterns
- [FastAPI request body docs](https://fastapi.tiangolo.com/tutorial/body/) - request validation model usage
- [FastAPI response model docs](https://fastapi.tiangolo.com/tutorial/response-model/) - response contract enforcement/filtering
- [FastAPI lifespan docs](https://fastapi.tiangolo.com/advanced/events/) - startup/shutdown lifecycle pattern
- [FastAPI error handling docs](https://fastapi.tiangolo.com/tutorial/handling-errors/) - explicit API error mapping
- [Pydantic models docs](https://docs.pydantic.dev/latest/concepts/models/) - validation/serialization and strict config options
- [PyPI langgraph](https://pypi.org/project/langgraph/) - version/runtime constraints
- [PyPI langchain](https://pypi.org/project/langchain/) - version/runtime constraints
- [PyPI langchain-openai](https://pypi.org/project/langchain-openai/) - provider integration version
- [PyPI fastapi](https://pypi.org/project/fastapi/) - API framework version
- [PyPI pydantic](https://pypi.org/project/pydantic/) - schema library version
- [PyPI uvicorn](https://pypi.org/project/uvicorn/) - ASGI runtime version

### Secondary (MEDIUM confidence)
- None required; primary sources sufficiently cover implementation decisions.

### Tertiary (LOW confidence)
- [Web discovery result: create_react_agent how-to path](https://langchain-ai.github.io/langgraph/how-tos/create-react-agent/) - used only as corroborating context, not primary basis.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - verified with official docs + current PyPI pages
- Architecture: HIGH - directly grounded in official LangChain/LangGraph/FastAPI patterns
- Pitfalls: MEDIUM - partially derived from documented behavior plus implementation-risk synthesis

**Research date:** 2026-03-17  
**Valid until:** 2026-04-16
