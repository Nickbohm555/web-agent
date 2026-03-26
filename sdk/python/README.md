# web-agent-sdk

Small Python SDK for this repo's two stable search entrypoints:

- `quick_search(...)` posts to the frontend `/api/search` route
- `agentic_search(...)` posts to the backend `/api/agent/run` route with `mode="agentic"`

## Install

```bash
pip install web-agent-sdk
```

## Usage

```python
from web_agent_sdk import WebAgentClient

client = WebAgentClient(
    base_url="http://localhost:3000",
    backend_base_url="http://localhost:8000",
)

quick = client.quick_search("Find pricing", max_results=3)
agentic = client.agentic_search("Investigate this company")
```
