# web-agent

Lightweight local agent workflow for building and iterating on web apps with Codex.

The product now exposes `/` as a quick-search launcher and uses stable chat routes for the other two modes:

- `/agentic/:threadId` for persistent agentic chats

Python SDK support now lives under `sdk/python` with two explicit entrypoints:

- `quick_search(...)` for frontend-backed quick retrieval via `/api/search`
- `agentic_search(...)` for backend-backed one-shot agent execution via `/api/agent/run`
- PyPI package: `https://pypi.org/project/web-agent-sdk/0.1.1/`
- GitHub repo: `https://github.com/Nickbohm555/web-agent`

## Included

- `agents.md`: operating instructions for the agent
- `prompt_build.md`: implementation prompt template
- `loop.sh`: repeatable Ralph-style execution loop
