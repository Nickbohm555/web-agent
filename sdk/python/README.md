# web-agent-sdk

Small Python SDK for stateless OpenAI-backed search runs:

- `quick_search(query)` for a fast web-backed answer
- `agentic_search(query)` for a deeper single-run investigation

Project links:

- PyPI: `https://pypi.org/project/web-agent-sdk/0.2.0/`
- GitHub: `https://github.com/Nickbohm555/web-agent`

## Install

```bash
pip install web-agent-sdk
```

## Usage

```python
from web_agent_sdk import WebAgentClient

client = WebAgentClient(api_key="your-openai-key", model="gpt-5.4")

quick = client.quick_search("Find pricing")
agentic = client.agentic_search("Investigate this company")
```
