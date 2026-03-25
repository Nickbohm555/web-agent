# Chat-Based Agentic And Deep Research Design

## Goal

Replace the current run-centric product flow for `agentic` and `deep_research` with thread-based chat experiences while keeping `/` as a quick-search launcher only.

## Summary

The application should expose three clearly different product surfaces:

- `/` for quick search only
- `/agentic/:threadId` for persistent agentic-search chat
- `/deep-research/:threadId` for persistent deep-research chat

`agentic` and `deep_research` should no longer be launched as variants of the same "start run" form. They should become dedicated chat pages backed by stable thread IDs, backend-owned transcripts, and Postgres-backed conversational continuity.

The legacy `/api/agent/run` launcher path remains available only for `quick`. Any `agentic` or `deep_research` start attempt through that route should fail with an explicit typed error that points callers to the chat routes.

This change removes the current deep-research job queue UX from the product path. Deep research becomes a normal back-and-forth chat where each user message triggers a coordinator invocation. The coordinator uses accumulated message history to decide whether enough context has been gathered and, once it has, decomposes the problem into parallel sub-research tasks for constrained subagents.

## Product Flow

### Quick Search

`/` remains the quick-search start page.

- It only supports `quick`.
- It accepts a prompt and runs the current quick-search flow synchronously.
- The `agentic` and `deep_research` options are removed from this launcher.

### Agentic Search

`/agentic/:threadId` becomes a dedicated conversational search page.

- The page loads prior transcript from the backend.
- The page renders the normal visible back-and-forth chat history.
- Sending a message invokes the agentic runtime for that thread.
- Conversation memory persists across turns through a Postgres checkpointer.
- New conversations start by creating a backend-owned thread, then navigating to its stable URL.

### Deep Research

`/deep-research/:threadId` becomes a dedicated conversational research page.

- The page loads prior transcript from the backend.
- The page renders only user messages and final assistant answers.
- Sending a message invokes a deep-research coordinator for that thread.
- There is no queued-job UX in the visible product flow.
- There is no progress timeline in the visible conversation.
- New conversations start by creating a backend-owned thread, then navigating to its stable URL.

## Non-Goals

- Do not keep `agentic` and `deep_research` as options on the `/` launcher.
- Do not preserve the current deep-research queued-job UX as the primary product path.
- Do not introduce `context.json` or a separate briefing artifact as a first-version dependency.
- Do not expose planner steps, subagent outputs, or internal reasoning in the visible chat transcript.
- Do not force a single over-generalized runtime abstraction that hides mode-specific behavior.

## User Experience Requirements

### Shared Chat Expectations

Both `/agentic/:threadId` and `/deep-research/:threadId` must:

- be addressable by stable URL thread ID
- reload deterministically from backend-owned transcript data
- render normal chat history from the backend
- append new turns without reconstructing history from run events

### Agentic UX

The agentic page should feel like a persistent search conversation:

- prior messages remain visible on refresh
- each new turn builds on the conversation so far
- final answers may include source metadata and citations

### Deep Research UX

The deep-research page should feel like a persistent research conversation:

- prior research turns remain visible on refresh
- only final assistant answers appear in the conversation
- internal research orchestration remains hidden

## Thread Lifecycle

Thread creation must be explicit rather than inferred from the first message.

Recommended flow:

1. The frontend offers distinct entry points for starting a new `agentic` chat and a new `deep research` chat.
2. Clicking one of those actions calls a create-thread endpoint for that mode.
3. The backend creates a stable `thread_id` and returns thread metadata.
4. The frontend navigates to `/agentic/:threadId` or `/deep-research/:threadId`.
5. The user sends the first message through the normal post-message endpoint on that page.

This keeps thread ID ownership in the backend contract instead of relying on frontend-generated IDs.

## Architecture

## Guiding Principles

- Keep runtime paths explicit.
- Keep files small and task-focused.
- Separate shared chat infrastructure from mode-specific reasoning.
- Use explicit Pydantic request/response models for frontend-facing contracts.

### Shared Chat Infrastructure

Add a focused shared thread/message layer responsible for:

- thread lookup and lifecycle
- transcript persistence
- transcript retrieval
- request/response schemas for chat APIs
- route handlers for reading a thread and posting a message

This shared layer should not decide how `agentic` or `deep_research` reason. It only owns the common chat contract and transcript mechanics.

### Agentic Runtime

Add a dedicated `agentic` chat runtime that:

1. accepts `thread_id` and a new user message
2. appends the user message to the transcript
3. invokes the agentic runtime bound to the same thread ID
4. uses Postgres checkpointer-backed conversational memory
5. captures the final assistant answer
6. appends the assistant answer to the transcript
7. returns the assistant message plus any user-facing sources metadata

This replaces the current stateless behavior where each invocation starts with empty memory.

### Deep Research Runtime

Add a dedicated deep-research chat runtime instead of adapting the queued-job runtime.

For each user turn it should:

1. accept `thread_id` and a new user message
2. append the user message to the transcript
3. load prior history for that thread
4. invoke the coordinator with thread-scoped history
5. let the coordinator decide whether enough context has been gathered
6. when enough context exists, decompose the work into subquestions or subsections
7. spawn parallel subagents constrained to `web_search` and `open_url`
8. synthesize one final assistant answer
9. append only that final assistant answer to the transcript
10. return the assistant message to the frontend

The current deep-research queued/background runtime should be removed from the product path.

Each deep-research turn must still end with exactly one visible assistant message in the transcript.

- If the coordinator decides enough context has not yet been gathered, it should return one user-facing assistant reply for that turn that summarizes current findings, uncertainty, and the best answer so far without exposing internal planning details.
- If the coordinator decides enough context has been gathered, it should decompose into subquestions or subsections, run constrained subagents in parallel, and return a synthesized assistant answer for that turn.

This keeps deep research as a normal visible back-and-forth conversation even before decomposition mode is reached.

## Persistence Model

### Transcript

The backend must persist normalized chat messages explicitly rather than reconstructing visible history from run events, artifact files, or checkpointer internals.

Each transcript record should at minimum include:

- `thread_id`
- `message_id`
- `role`
- `content`
- `created_at`
- optional user-facing citations or sources for assistant turns

The transcript is the visible source of truth for the UI.

### Checkpointer

The Postgres checkpointer remains an internal state mechanism, not the UI transcript source.

For `agentic`, the checkpointer stores conversational memory for the thread.

For `deep_research`, the checkpointer stores coordinator and subagent continuity as needed for the thread. It should not replace explicit transcript persistence.

### No `context.json`

Do not create or maintain `/context.json` in the first version.

The coordinator should use message history to determine whether enough context has been gathered. If future evidence shows the coordinator needs a compact derived briefing, that can be introduced later as derived state, not as a parallel source of truth from the start.

## API Design

The frontend-facing chat contract should move away from the run-start-only abstraction for `agentic` and `deep_research`.

Introduce explicit thread/message APIs with feature-local schemas. The exact route names can follow existing conventions, but the contract needs to cover:

- creating a thread for a specific mode
- loading a thread and its ordered transcript
- posting a new user message to a thread
- returning the appended assistant response
- returning typed error payloads

Recommended schema categories:

- thread summary
- create-thread request
- create-thread response
- chat message
- get-thread response
- post-message request
- post-message response
- chat error response

These schemas should live in a feature-local `schemas/` folder rather than a generic catch-all schema file.

At minimum, the shared chat contract should make these shapes explicit:

- thread metadata: `thread_id`, `mode`, `title | null`, `created_at`, `updated_at`
- message: `message_id`, `thread_id`, `role`, `content`, `created_at`, `sources | null`
- post-message request: `content` plus a client-supplied idempotency key for safe retries
- post-message response: appended `user_message`, final `assistant_message`, and updated thread metadata

For the first implementation plan, the assistant `sources` payload only needs enough structure for safe citation rendering. It does not need to expose internal tool traces.

## Transport Model

For the first version, both `agentic` and `deep research` should use a chat-native post-message request/response contract rather than the current queued-job API.

- `agentic` remains a standard synchronous post-message request.
- `deep research` also uses a post-message request that returns one assistant message for the turn.
- the first deep-research implementation should target a single-request completion budget of roughly 60 seconds end to end
- if a deep-research turn exceeds that budget, the backend should return a typed timeout-style error for the turn rather than silently switching to a queued or pending-turn transport

If runtime evidence later shows that some deep-research turns exceed normal request limits, a thread-scoped pending-turn transport can be designed separately. That is a follow-up optimization, not a requirement of this spec.

## Suggested Module Layout

To keep the runtime explicit and avoid monolithic orchestration files, split the work into focused modules such as:

- `backend/api/routes/chat_threads.py`
- `backend/api/services/chat_threads.py`
- `backend/api/schemas/chat/thread.py`
- `backend/api/schemas/chat/message.py`
- `backend/api/schemas/chat/post_message.py`
- `backend/agent/chat_history/`
- `backend/agent/agentic_chat_runtime.py`
- `backend/agent/deep_research_chat_runtime.py`
- `backend/agent/deep_research/coordinator.py`
- `backend/agent/deep_research/history_inspection.py`
- `backend/agent/deep_research/decomposition.py`
- `backend/agent/deep_research/synthesis.py`

Exact filenames may vary, but the separation of responsibilities should remain.

## Deep Research Coordinator Design

The deep-research coordinator prompt should be rewritten for conversational accumulation rather than background job stages.

Its core decision is:

- continue gathering context from prior conversation and retrieval
- or conclude that enough context exists and decompose into parallel research tasks

Once enough context exists, the coordinator should:

1. define focused subquestions or subsections
2. dispatch constrained subagents in parallel
3. collect their outputs
4. synthesize a final user-facing answer that responds to the current thread state and latest user request

Subagents should:

- be constrained to research execution rather than final-answer ownership
- have access only to `web_search` and `open_url`
- return structured research results to the coordinator

The coordinator remains responsible for the final answer shown to the user.

## Error Handling

### Shared Expectations

- Errors must remain typed and safe for the frontend.
- Existing transcript history must remain intact on failure.
- Failed turns should not corrupt thread state.
- retried post-message requests must deduplicate safely by idempotency key so the same user turn is not appended twice

### Agentic

If an agentic invocation fails:

- the post-message endpoint returns a typed error
- the UI keeps the prior chat history visible
- the UI can preserve draft/retry affordances separately from transcript persistence

### Deep Research

If one or more subagents fail:

- the coordinator may still synthesize a final answer if enough evidence exists
- the final answer may acknowledge coverage gaps when necessary

If the top-level coordinator invocation fails:

- the post-message endpoint returns a typed error
- no partial internal orchestration is appended as a visible assistant message

## Frontend Impact

### Launcher

Update the existing run launcher so it only exposes quick search.

### New Pages

Add separate frontend pages for:

- `agentic` chat
- `deep research` chat

These pages should:

- fetch transcript by thread ID on load
- render ordered messages from the backend
- submit new user messages to a thread-scoped endpoint
- append returned assistant messages to the visible conversation

The visible model should be chat-native rather than run-event-native for these two surfaces.

## Migration Notes

- The current deep-research queue/job code should be removed from the user-facing flow.
- Existing run-event streaming can remain for quick search if still useful there, but it should not dictate the chat contract for `agentic` and `deep research`.
- Existing deep-agent persistence pieces may be reused where they cleanly support stable thread continuity, but transcript persistence should be explicit and separate.
- legacy launcher paths should stop offering `agentic` and `deep_research`, and any obsolete frontend code tied to their run-based entry flow should be removed once the new chat pages replace it

## Testing Strategy

Add or update tests to cover:

- quick launcher exposes quick-search behavior only
- `/agentic/:threadId` loads and renders persisted transcript
- `/deep-research/:threadId` loads and renders persisted transcript
- agentic memory persists across multiple turns through Postgres checkpointer
- deep-research history influences later turns
- deep-research coordinator can switch from gathering mode to decomposition mode based on accumulated history
- deep-research subagents are invoked in parallel with only `web_search` and `open_url`
- only final assistant answers are appended to transcript for deep research
- typed error responses remain frontend-safe
- queued-job endpoints and frontend paths are removed or no longer used for deep-research chat

## Recommended Implementation Order

1. Introduce shared transcript schemas and thread/message APIs.
2. Build the new `agentic` chat page and thread-backed runtime.
3. Build the new `deep research` chat page and coordinator-backed runtime.
4. Remove deep-research queued-job product flow and obsolete frontend coupling.
5. Tighten tests around persistence, routing, and deep-research decomposition behavior.

## Decision

Implement option 1:

- `/` stays quick-search only
- `agentic` gets its own stable-thread chat page
- `deep research` gets its own stable-thread chat page
- deep research stops being a queued job and becomes a conversational coordinator flow
- the coordinator uses message history, not `context.json`, to decide when to decompose into parallel sub-research
