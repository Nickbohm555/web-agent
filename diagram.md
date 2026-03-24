# Prompt To Response Decision Tree

This file shows the live runtime split from one incoming prompt to the final response envelope.

## Shared Request Contract

- Browser entrypoint: `POST /api/runs` in `src/frontend/routes/runs.ts`
- Backend execution entrypoint: `POST /api/agent/run` in `backend/api/routes/agent_run.py`
- Request model: `AgentRunRequest` in `backend/api/contracts.py`

```json
{
  "prompt": "string",
  "mode": "quick | agentic | deep_research",
  "retrieval_policy": {
    "search": {
      "country": "US",
      "language": "en",
      "freshness": "any | day | week | month | year",
      "include_domains": [],
      "exclude_domains": []
    },
    "fetch": {
      "max_age_ms": 300000,
      "fresh": false
    }
  }
}
```

## Decision Tree

```text
Prompt
└── POST /api/runs
    └── POST /api/agent/run
        └── run_agent_once
            └── resolve retrieval policy
                ├── quick
                │   └── quick profile
                │       └── run_quick_search
                │           └── run_web_search
                │               └── quick answer
                │                   └── success response
                ├── agentic
                │   └── agentic profile
                │       └── build agent and config
                │           ├── web_search
                │           │   └── search response
                │           └── open_url
                │               └── crawl response
                │                   └── final answer and sources
                │                       └── success response
                └── deep_research
                    └── deep research profile
                        └── build agent and config
                            ├── web_search
                            │   └── search response
                            └── open_url
                                └── crawl response
                                    └── final answer and sources
                                        └── success response
```

## Branch Inputs

### 1. Quick Search

- Runtime call:

```python
run_agent_once(
    prompt=prompt,
    mode="quick",
    retrieval_policy=effective_policy,
)
```

- Runtime profile:

```json
{
  "name": "quick",
  "model": "gpt-4.1-mini",
  "recursion_limit": 4,
  "timeout_seconds": 20,
  "execution_mode": "single_pass",
  "max_tool_steps": 1,
  "max_search_results": 5,
  "max_crawl_chars": 0
}
```

- Search call shape:

```json
{
  "query": "<prompt plus optional site: / -site: terms>",
  "max_results": 5,
  "freshness": "<policy.search.freshness>"
}
```

- Response path:
  `WebSearchResponse -> synthesize_quick_answer() -> AgentRunResult -> AgentRunSuccessResponse`

### 2. Agentic Search

- Runtime call:

```python
run_agent_once(
    prompt=prompt,
    mode="agentic",
    retrieval_policy=effective_policy,
)
```

- Runtime profile:

```json
{
  "name": "agentic",
  "model": "gpt-4.1-mini",
  "recursion_limit": 12,
  "timeout_seconds": 45,
  "execution_mode": "bounded_agent_loop",
  "max_tool_steps": 6,
  "max_search_results": 4,
  "max_crawl_chars": 4000
}
```

- Agent invoke input:

```json
{
  "messages": [
    {
      "role": "user",
      "content": "<prompt>"
    }
  ]
}
```

- Agent config input:

```json
{
  "recursion_limit": 12,
  "run_mode": "agentic",
  "execution_mode": "bounded_agent_loop",
  "timeout_seconds": 45,
  "model": "gpt-4.1-mini",
  "tool_limits": {
    "max_tool_steps": 6,
    "max_search_results": 4,
    "max_crawl_chars": 4000
  },
  "retrieval_policy": "<effective policy>"
}
```

### 3. Deep Research

- Runtime call:

```python
run_agent_once(
    prompt=prompt,
    mode="deep_research",
    retrieval_policy=effective_policy,
)
```

- Runtime profile:

```json
{
  "name": "deep_research",
  "model": "gpt-4.1",
  "recursion_limit": 24,
  "timeout_seconds": 180,
  "execution_mode": "background_research",
  "max_tool_steps": 16,
  "max_search_results": 8,
  "max_crawl_chars": 12000
}
```

- Agent invoke input:

```json
{
  "messages": [
    {
      "role": "user",
      "content": "<prompt>"
    }
  ]
}
```

- Agent config input:

```json
{
  "recursion_limit": 24,
  "run_mode": "deep_research",
  "execution_mode": "background_research",
  "timeout_seconds": 180,
  "model": "gpt-4.1",
  "tool_limits": {
    "max_tool_steps": 16,
    "max_search_results": 8,
    "max_crawl_chars": 12000
  },
  "retrieval_policy": "<effective policy>"
}
```

## Tool Input Shapes

### `web_search`

- LangChain tool name: `web_search`
- Input schema: `WebSearchInput`

```json
{
  "query": "string",
  "max_results": 1
}
```

- Effective runtime call:

```json
{
  "query": "<query plus optional domain scope terms>",
  "max_results": "<min(requested, mode cap)>",
  "freshness": "any | day | week | month | year"
}
```

- Success payload:

```json
{
  "query": "string",
  "results": [
    {
      "title": "string",
      "url": "https://example.com",
      "snippet": "string",
      "rank": {
        "position": 1,
        "provider_position": 1,
        "rerank_score": 0.98
      }
    }
  ],
  "metadata": {
    "result_count": 1,
    "provider": "serper"
  },
  "meta": {
    "...": "tool telemetry"
  }
}
```

### `open_url`

- LangChain tool name: `open_url`
- Input schema: `OpenUrlInput`

```json
{
  "url": "https://example.com/page",
  "objective": "Find the exact evidence needed from this page"
}
```

- Effective runtime call:

```json
{
  "url": "https://example.com/page",
  "objective": "optional string"
}
```

- Success payload:

```json
{
  "url": "https://example.com/page",
  "final_url": "https://example.com/page",
  "text": "string",
  "markdown": "string",
  "objective": "optional string",
  "excerpts": [
    {
      "text": "string",
      "markdown": "string"
    }
  ],
  "status_code": 200,
  "content_type": "text/html",
  "fallback_reason": null,
  "meta": {
    "...": "tool telemetry"
  }
}
```

## Final Response Contract

All three branches normalize back into the same backend response shape:

```json
{
  "run_id": "uuid",
  "status": "completed",
  "final_answer": {
    "text": "string",
    "citations": [],
    "basis": []
  },
  "sources": [
    {
      "source_id": "string",
      "title": "string",
      "url": "https://example.com",
      "snippet": "string"
    }
  ],
  "tool_call_count": 0,
  "elapsed_ms": 0,
  "metadata": {
    "tool_call_count": 0,
    "elapsed_ms": 0
  }
}
```

## Implemented Features

These are the feature areas from [`clone.md`](/Users/nickbohm/Desktop/Tinkering/web-agent/clone.md) that are implemented in this repo today and where they appear in the runtime tree above.

### 1. Search API Natural-Language Web Search With Agent-Facing Excerpts

- Implemented here as `web_search` plus quick-mode single-pass search.
- Runtime path: `run_quick_mode -> run_quick_search -> run_web_search` and agent tool path `web_search -> run_web_search`.
- Current repo behavior includes query-aware reranking, tighter excerpts, normalized result metadata, and shared source extraction.

### 2. Extract API Objective-Driven Page Extraction

- Implemented here as `open_url`.
- Runtime path: `open_url -> run_open_url -> HttpFetchWorker.fetch -> extract_content`.
- Current repo behavior includes optional `objective` input, excerpt selection for long pages, normalized markdown/text output, and fallback handling for low-quality or unsupported content.

### 3. Source Policy Domain And Freshness Controls

- Implemented here as `retrieval_policy` on the shared run request contract.
- Runtime path: `AgentRunRequest.retrieval_policy -> resolve_effective_retrieval_policy -> tool wrappers and quick search inputs`.
- Current repo behavior includes include/exclude domain controls, freshness controls, and prompt-driven policy inference for official-source and recency intent.

### 4. Multi-Mode Grounded Run Profiles

- Implemented here as the shared `quick`, `agentic`, and `deep_research` modes.
- Runtime path: `run_agent_once -> resolve_effective_retrieval_policy -> get_runtime_profile -> mode branch`.
- Current repo behavior keeps one browser/backend contract while switching model, execution mode, tool budgets, and background-research depth by profile.

### 5. Citation-Rich Structured Answers And Source Lists

- Implemented here in the final backend response contract and frontend completion handling.
- Runtime path: `extract_final_answer plus extract_sources -> AgentRunSuccessResponse`.
- Current repo behavior returns structured answer content, normalized `sources`, and frontend-renderable citation data instead of only a flat answer string.

### 6. Granular Basis Verification

- Implemented here in the structured answer payload.
- Runtime path: final answer assembly after agent execution, before `AgentRunSuccessResponse`.
- Current repo behavior supports optional per-claim and per-list-item `basis` evidence references validated against the safe source registry.

### 7. Streaming Retrieval Transparency And Run History

- Implemented here in the browser route and client state layers around the same runtime.
- Runtime path: `src/frontend/routes/runs.ts` emits run events that the client and stored history replay consume.
- Current repo behavior streams typed search/crawl/verification milestones, preserves them in run history, and rehydrates them in the frontend timeline.

## Source Files

- `src/frontend/routes/runs.ts`
- `backend/api/contracts.py`
- `backend/api/routes/agent_run.py`
- `backend/api/services/agent_run.py`
- `backend/agent/runtime_execution.py`
- `backend/agent/runtime_constants.py`
- `backend/agent/runtime_policy.py`
- `backend/agent/quick_search.py`
- `backend/app/contracts/web_search.py`
- `backend/app/contracts/open_url.py`
- `backend/app/tools/web_search.py`
- `backend/app/tools/open_url.py`
