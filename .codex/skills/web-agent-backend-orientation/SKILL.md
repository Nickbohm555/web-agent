---
name: web-agent-backend-orientation
description: Use when the user wants to understand this repo, especially backend architecture, runtime boundaries, request/data flow, or how major product features are implemented. Read `diagram.md` first, then inspect the referenced files only where the user's question needs more detail.
---

# Web Agent Backend Orientation

This skill is for explaining how the `web-agent` repo works, with emphasis on backend architecture and data movement.

## Workflow

1. Read `diagram.md` first.
2. Start from the live entrypoints before expanding outward:
   - `backend/main.py`
   - `backend/api/routes/agent_run.py`
   - `backend/api/routes/run_execution.py`
   - `backend/agent/runtime.py`
3. If the question is about tool internals, inspect:
   - `backend/app/tools/web_search.py`
   - `backend/app/tools/web_crawl.py`
   - `backend/app/providers/serper_client.py`
   - `backend/app/crawler/http_worker.py`
   - `backend/app/crawler/extractor.py`
4. If the question is about how the frontend uses the backend, inspect:
   - `src/frontend/server.ts`
   - `src/frontend/routes/runs.ts`
   - `src/frontend/client/api-client.ts`
5. Answer in this order unless the user asks for something narrower:
   - Current backend architecture
   - Step-by-step data flow
   - Main features and how each is built
   - Gaps, TODOs, or architecture that is planned but not yet implemented

## Response Rules

- Treat `diagram.md` as the current orientation artifact for this repo.
- Prefer concrete file-path evidence over generic architecture language.
- Call out when something is implemented in the Python backend versus the TypeScript frontend/API shim.
- Distinguish clearly between:
  - implemented flow
  - compatibility/shim flow
  - planned-but-not-yet-built flow from `.planning/`
- When the user asks for a diagram, provide a Mermaid diagram first unless they ask for another format.
- When you notice the repo has drifted from `diagram.md`, update `diagram.md` before answering.

## Scope Notes

- The canonical backend app is FastAPI in `backend/**`.
- The local UI and some API orchestration still live in `src/frontend/**`.
- Search and crawl are exposed as canonical tools: `web_search` and `web_crawl`.
- Retrieval policy is inferred and enforced in the agent runtime/tool layer, not in the UI.
