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

```mermaid
flowchart TD
    A[Prompt submitted from browser] --> B[POST /api/runs<br/>src/frontend/routes/runs.ts]
    B --> C[Proxy to backend executor]
    C --> D[POST /api/agent/run<br/>backend/api/routes/agent_run.py]
    D --> E[execute_agent_run_request(payload)]
    E --> F[run_agent_once(prompt, mode, retrieval_policy)]
    F --> G[resolve_effective_retrieval_policy(prompt, retrieval_policy)]
    G --> H{mode}

    H -->|quick| I[Quick search branch]
    H -->|agentic| J[Agentic branch]
    H -->|deep_research| K[Deep research branch]

    I --> I1[get_runtime_profile quick]
    I1 --> I2[profile<br/>model=gpt-4.1-mini<br/>execution_mode=single_pass<br/>recursion_limit=4<br/>max_tool_steps=1<br/>max_search_results=5<br/>max_crawl_chars=0]
    I2 --> I3[run_quick_mode]
    I3 --> I4[run_quick_search inputs<br/>query=prompt<br/>max_results=5<br/>freshness=policy.search.freshness<br/>include_domains=policy.search.include_domains<br/>exclude_domains=policy.search.exclude_domains]
    I4 --> I5[run_web_search inputs<br/>query=scoped prompt with site terms if needed<br/>max_results=5<br/>freshness=policy.search.freshness]
    I5 --> I6[Serper search]
    I6 --> I7[WebSearchResponse]
    I7 --> I8[synthesize_quick_answer]
    I8 --> Z[AgentRunSuccessResponse]

    J --> J1[get_runtime_profile agentic]
    J1 --> J2[profile<br/>model=gpt-4.1-mini<br/>execution_mode=bounded_agent_loop<br/>recursion_limit=12<br/>max_tool_steps=6<br/>max_search_results=4<br/>max_crawl_chars=4000]
    J2 --> J3[build_system_prompt plus retrieval brief]
    J3 --> J4[build_runtime_config]
    J4 --> J5[agent.invoke inputs<br/>messages=[{role:user, content:prompt}]<br/>config.run_mode=agentic<br/>config.execution_mode=bounded_agent_loop<br/>config.tool_limits={steps:6, search:4, crawl:4000}<br/>config.retrieval_policy=effective policy]
    J5 --> J6[Agent may call web_search or web_crawl]
    J6 --> Z

    K --> K1[get_runtime_profile deep_research]
    K1 --> K2[profile<br/>model=gpt-4.1<br/>execution_mode=background_research<br/>recursion_limit=24<br/>max_tool_steps=16<br/>max_search_results=8<br/>max_crawl_chars=12000]
    K2 --> K3[build_system_prompt plus retrieval brief]
    K3 --> K4[build_runtime_config]
    K4 --> K5[agent.invoke inputs<br/>messages=[{role:user, content:prompt}]<br/>config.run_mode=deep_research<br/>config.execution_mode=background_research<br/>config.tool_limits={steps:16, search:8, crawl:12000}<br/>config.retrieval_policy=effective policy]
    K5 --> K6[Agent may call web_search or web_crawl]
    K6 --> Z

    J6 --> S[web_search tool]
    K6 --> S
    J6 --> T[web_crawl tool]
    K6 --> T

    S --> S1[LangChain tool name web_search]
    S1 --> S2[input schema WebSearchInput<br/>{ query: string, max_results: 1..10 }]
    S2 --> S3[tool wrapper applies caps and domain scope]
    S3 --> S4[run_web_search inputs<br/>query=possibly scoped query<br/>max_results=min(requested, profile cap)<br/>freshness=policy.search.freshness]
    S4 --> S5[SerperClient.search inputs<br/>query<br/>max_results<br/>freshness]
    S5 --> S6[WebSearchResponse<br/>{ query, results[], metadata, meta }]

    T --> T1[LangChain tool name web_crawl]
    T1 --> T2[input schema WebCrawlInput<br/>{ url: http/https URL, objective?: string }]
    T2 --> T3[tool wrapper rejects URLs outside policy search domain scope]
    T3 --> T4[run_web_crawl inputs<br/>url<br/>objective]
    T4 --> T5[HttpFetchWorker.fetch input<br/>url]
    T5 --> T6[extract_content inputs<br/>body<br/>content_type<br/>objective]
    T6 --> T7[WebCrawlSuccess<br/>{ url, final_url, text, markdown, objective, excerpts[], status_code, content_type, fallback_reason, meta }]

    Z --> Z1[extract_final_answer plus extract_sources]
    Z1 --> Z2[HTTP response AgentRunSuccessResponse<br/>{ run_id, status, final_answer, sources, tool_call_count, elapsed_ms, metadata }]
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

### `web_crawl`

- LangChain tool name: `web_crawl`
- Input schema: `WebCrawlInput`

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
- `backend/app/contracts/web_crawl.py`
- `backend/app/tools/web_search.py`
- `backend/app/tools/web_crawl.py`
