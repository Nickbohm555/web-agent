# web-agent

Lightweight local agent workflow for building and iterating on web apps with Codex.

The app currently exposes two main user-facing search experiences:

- `/` for the quick-search launcher
- `/agentic/:threadId` for persistent agentic chats

The Python SDK is published on PyPI as [`web-agent-sdk`](https://pypi.org/project/web-agent-sdk/0.2.0/) and documents two stable stateless entrypoints:

- `quick_search(query)` for a fast OpenAI-backed web answer
- `agentic_search(query)` for a deeper single-run investigation
- configure the client with only `api_key` and `model`

![web-agent quick search and agentic search workflow](docs/assets/readme-search-workflows.svg)

## Quick Search Vs. Agentic Search

### Quick search

Use quick search when you want a fast stateless answer grounded by OpenAI web search.

- SDK entrypoint: `WebAgentClient.quick_search(...)`
- Runtime path: the Python SDK calls the OpenAI Responses API with the user-supplied `model`, the built-in web search tool, and `store=False`
- Best fit: quick fact-finding, lightweight retrieval, and low-latency answers without server-side memory

### Agentic search

Use agentic search when you want a deeper single-run investigation without any attached memory or server-side database state.

- SDK entrypoint: `WebAgentClient.agentic_search(...)`
- Runtime path: the Python SDK calls the OpenAI Responses API with the user-supplied `model`, the built-in web search tool, and `store=False`
- Best fit: investigations, synthesis, and single-shot answers where the user controls the model and API key

## How The Workflow Fits Together

The diagram above now describes the product split conceptually, but the published Python SDK itself is stateless and OpenAI-native as of `web-agent-sdk` `0.2.0`.

- The quick path asks OpenAI to answer quickly with web search.
- The agentic path asks OpenAI to perform a more thorough single-pass investigation with web search.
- In practice: choose `quick_search(...)` for speed, and choose `agentic_search(...)` for deeper synthesis.

## Python SDK

Install from PyPI:

```bash
pip install web-agent-sdk
```

Published usage example:

```python
from web_agent_sdk import WebAgentClient

client = WebAgentClient(api_key="your-openai-key", model="gpt-5.4")

quick = client.quick_search("Find pricing")
agentic = client.agentic_search("Investigate this company")
```

## Included

- `AGENTS.md`: operating instructions for the agent
- `prompt_build.md`: implementation prompt template
- `loop.sh`: repeatable Ralph-style execution loop
