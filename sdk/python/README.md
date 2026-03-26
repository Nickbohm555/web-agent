# web-agent-sdk

Python SDK for stateless OpenAI-backed web search runs, driven by an injected `langchain_openai.ChatOpenAI` model.

Project links:

- PyPI: `https://pypi.org/project/web-agent-sdk/0.3.1/`
- GitHub: `https://github.com/Nickbohm555/web-agent`

## Why This Exists

This package exists to show that web search agents can stay small and cheap.

The core design is just:

1. `web_search` to get candidate URLs
2. `open_url` to retrieve page content
3. an LLM to synthesize the answer from the returned evidence

## Install

```bash
pip install web-agent-sdk
```

## Usage

```python
from langchain_openai import ChatOpenAI

from web_agent_sdk import WebAgentClient

llm = ChatOpenAI(
    model="gpt-5-nano",
    api_key="your-openai-key",
)

client = WebAgentClient(chat_model=llm)

quick = client.quick_search("Find pricing")
agentic = client.agentic_search("Investigate this company")
```

## Behavior

- `quick_search(query)` runs a fast stateless OpenAI Responses API search with the built-in `web_search` tool
- `agentic_search(query)` runs a more thorough stateless OpenAI Responses API search with the same tool
- the SDK derives the OpenAI model name and API key from the injected `ChatOpenAI` instance
- the backend uses a simple two-tool web workflow rather than an all-in-one proprietary research API

## Inspiration

This package was inspired in part by Onyx's article: `https://onyx.app/blog/building-the-best-deep-research`
