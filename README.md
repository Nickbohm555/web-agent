# web-agent

Lightweight local agent workflow for building and iterating on web apps with Codex.

The product now exposes `/` as a quick-search launcher and uses stable chat routes for the other two modes:

- `/agentic/:threadId` for persistent agentic chats
- `/deep-research/:threadId` for persistent deep-research chats

## Included

- `agents.md`: operating instructions for the agent
- `prompt_build.md`: implementation prompt template
- `loop.sh`: repeatable Ralph-style execution loop
