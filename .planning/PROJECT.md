# Python LangGraph Web Agent Demo

## What This Is

A local-first demo app that runs a single ReAct-style LangGraph agent in Python with two tools: web search and in-house web crawl. It is built to make backend tool behavior easy to inspect from a simple TypeScript frontend and Docker logs. The target user is the builder (you) validating agent behavior quickly during a large TypeScript-to-Python backend refactor.

## Core Value

A user can run one prompt from a simple UI and clearly see how the agent invokes search and crawl tools end-to-end.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Build Python backend using LangGraph ReAct-style agent with two tools (`web_search`, `web_crawl`).
- [ ] Integrate Serper for search using `SERPER_API_KEY` from environment variables.
- [ ] Use OpenAI model provider with `OPENAI_API_KEY` from environment variables.
- [ ] Build an in-house crawler tool in Python (simple v1 implementation).
- [ ] Provide a TypeScript frontend with a minimal UI to run the agent.
- [ ] Show full tool inputs and outputs in UI/logging for debugging and validation.
- [ ] Run locally with Docker Compose and inspect behavior through Docker logs.
- [ ] Replace current TypeScript backend path with Python backend for this v1.

### Out of Scope

- User authentication/authorization — excluded to keep v1 focused on tool execution observability.
- Advanced crawler sophistication (deep compliance and browser automation) — deferred to keep v1 implementation simple.
- Multi-agent orchestration — excluded because v1 scope is one simple agent with two tools.
- Deployment/production hardening — deferred; local Docker Compose is sufficient for initial validation.

## Context

This repository already contains substantial TypeScript implementation and tests, but the current goal is to shift the agent/tool backend path to Python while keeping a TypeScript frontend for quick testing. The key need is observability: understanding exactly what inputs are sent to each tool and what outputs are returned, not polishing product UX. Serper will power search, and an in-house crawler will fetch/extract content similarly to the tool split used by modern internet-search agent systems.

## Constraints

- **Stack**: Python backend + LangGraph agent + TypeScript frontend — required to align with refactor target and UI needs.
- **Model provider**: OpenAI — chosen explicitly by user for v1.
- **Search provider**: Serper — selected tool API with environment-provided key.
- **Runtime**: Local Docker Compose — required for local development and log visibility.
- **Observability**: Full tool inputs/outputs visible — needed to validate how agent tools run.
- **Scope**: Keep implementation simple (no auth, minimal UI) — prevents scope creep during major refactor.
- **Delivery**: Balanced speed/quality — not throwaway, but avoid overengineering.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Use Python backend with LangGraph ReAct-style agent | Align with full backend refactor target | — Pending |
| Keep exactly two v1 tools: search + crawl | Mirrors intended agent behavior and keeps tool surface focused | — Pending |
| Use OpenAI + Serper via env keys | Explicit user choice and existing key setup | — Pending |
| Replace TypeScript backend now | User requested immediate cutover strategy | — Pending |
| Local Docker Compose only for v1 | Simplifies execution and debugging loop | — Pending |
| Minimal TypeScript UI with clear run visibility | Primary value is backend observability, not feature-rich frontend | — Pending |
| Full tool input/output visibility | Needed to verify agent behavior and debug rapidly | — Pending |
| Exclude auth and other platform features | Keeps v1 tightly focused and achievable | — Pending |

---
*Last updated: 2026-03-17 after initialization*
