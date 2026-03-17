# Phase 04: Frontend Prompt Execution Surface - Research

**Researched:** 2026-03-17  
**Domain:** Minimal TypeScript execution UI + live run/tool progress streaming  
**Confidence:** HIGH

## Summary

Phase 04 should be planned around a minimal, single-run UI with a strict client-side state machine and a server-driven event stream for progress updates. The current repo already has an Express TypeScript surface with Zod-validated envelopes and route-contract tests, so the fastest path is to keep that contract-first style and add a run-oriented API client and timeline renderer rather than introducing heavyweight frontend framework complexity.

For run progress, the standard fit is HTTP Server-Sent Events (SSE): one-way server-to-client updates over `text/event-stream`, typed named events, built-in browser reconnection, and low implementation overhead for local Docker workflows. This matches the phase objective (display transitions + per-tool status/duration) and aligns with LangGraph's streaming model, which can emit structured updates/custom events from agent and tool execution.

**Primary recommendation:** Use a two-step execution flow (`POST /api/runs` + `GET /api/runs/:runId/events` SSE) with a typed run-state reducer in TypeScript, and treat backend-emitted tool timings as source of truth for timeline duration display.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library / Standard | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| TypeScript | `^5.9` (repo) | Typed UI state, API contracts, reducers | Already adopted in repo; required for reliable contract coupling |
| Express API surface | `^5.2.1` (repo) | Backend HTTP endpoints consumed by UI | Already in use for existing `/api` routes and easy extension |
| Zod | `^4.3.6` (repo) | Runtime validation of request/response/event payloads | Existing project pattern; catches schema drift early |
| SSE (`EventSource`) | Web standard (baseline since Jan 2020) | Real-time run/tool progress updates | Minimal complexity for one-way progress stream, native browser support |

### Supporting
| Library / Standard | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| LangGraph streaming (`stream(..., version="v2")`) | LangGraph `>=1.1` | Unified stream parts (`type`, `ns`, `data`) from graph execution | Use in backend Phase 3+ to produce structured execution events |
| FastAPI `StreamingResponse` (or equivalent) | Current FastAPI docs | Emit `text/event-stream` from Python backend | Use when backend execution service is Python-native |
| Vitest | `^4.1.0` (repo) | Reducer/client contract tests | Use for UI state transitions and event handling correctness |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| SSE for progress feed | WebSocket | More setup and bidirectional complexity without clear Phase 04 need |
| SSE push updates | Poll `/runs/:id` repeatedly | Simpler server, but chattier network and coarser progress UX |
| Vanilla TypeScript view | React + query/state libs | Better long-term scalability, but slows minimal surface delivery |

**Installation (only if adding missing pieces):**
```bash
npm install zod
npm install -D vitest
```

## Architecture Patterns

### Recommended Project Structure
```text
src/
├── frontend/
│   ├── app/
│   │   ├── state.ts         # Run state machine + reducer (single source of truth)
│   │   ├── api-client.ts    # POST run + SSE subscribe logic
│   │   ├── timeline.ts      # Tool event mapping and duration formatting
│   │   └── render.ts        # Minimal DOM rendering/update layer
│   ├── contracts.ts         # Zod schemas (extend with run/event contracts)
│   └── server.ts            # Existing HTTP/static/API wiring
└── tests/
    ├── frontend/
    │   ├── state.test.ts
    │   ├── api-client.test.ts
    │   └── timeline.test.ts
    └── frontend-api/
        └── runs.contracts.test.ts
```

### Pattern 1: Two-step run lifecycle API
**What:** Start a run with `POST`, then stream lifecycle/tool updates over SSE using `runId`.  
**When to use:** Any run that may take multiple tool calls and needs incremental UI updates.
**Example:**
```typescript
// Source: MDN SSE docs + existing repo contract pattern
const start = await fetch("/api/runs", {
  method: "POST",
  headers: { "content-type": "application/json" },
  body: JSON.stringify({ prompt }),
});
const { runId } = await start.json();

const events = new EventSource(`/api/runs/${runId}/events`);
events.addEventListener("run_state", (e) => onRunState(JSON.parse(e.data)));
events.addEventListener("tool_call", (e) => onToolCall(JSON.parse(e.data)));
events.addEventListener("run_complete", (e) => onComplete(JSON.parse(e.data)));
events.addEventListener("run_error", (e) => onError(JSON.parse(e.data)));
```

### Pattern 2: Explicit frontend run state machine
**What:** Enforce legal state transitions with a reducer and discriminated union events.  
**When to use:** Always; prevents invalid UI states (e.g., completed run receiving "queued" state).
**Example:**
```typescript
type RunPhase = "idle" | "starting" | "running" | "succeeded" | "failed";

type AppEvent =
  | { type: "run_started"; runId: string; startedAt: number }
  | { type: "run_state"; state: "queued" | "running" | "completed" | "failed"; at: number }
  | { type: "tool_call"; tool: "web_search" | "web_crawl"; status: "started" | "succeeded" | "failed"; at: number; durationMs?: number }
  | { type: "stream_error"; message: string };
```

### Pattern 3: Server-authoritative timeline durations
**What:** Render durations from backend event payload (`durationMs`) when available; derive provisional elapsed time client-side only while in-flight.  
**When to use:** Tool status rows in progress timeline.

### API Contract Assumptions and Validation Points

Plan Phase 04 work assuming Phase 3 exposes (or can add) these contracts:

1. `POST /api/runs`
   - Request: `{ prompt: string }`
   - Response: `{ runId: string, status: "queued" | "running" }`
   - Validation: prompt non-empty/min length, runId format, status enum

2. `GET /api/runs/:runId/events` (`text/event-stream`)
   - Named events:
     - `run_state`: `{ runId, state, ts }`
     - `tool_call`: `{ runId, toolCallId, toolName, status, startedAt, endedAt?, durationMs?, inputPreview?, outputPreview?, error? }`
     - `run_complete`: `{ runId, finalAnswer, completedAt, durationMs }`
     - `run_error`: `{ runId, message, code?, failedAt }`
   - Validation:
     - `toolName` must be exactly `"web_search"` or `"web_crawl"` (locked project decision)
     - state transitions monotonic (`queued -> running -> completed|failed`)
     - `durationMs >= 0`
     - optional sequence/event id for ordering/replay

3. Optional fallback: `GET /api/runs/:runId`
   - Use if SSE drops and replay is needed for final consistency.

### UI State Model Suggestions

Use one state object per active run:

- `run`: `{ id, phase, prompt, startedAt, endedAt?, finalAnswer?, error? }`
- `timeline`: ordered array keyed by `toolCallId`:
  - `toolName`, `status`, `startedAt`, `endedAt?`, `durationMs?`, `error?`
- `connection`: `connecting | open | retrying | closed`
- `lastEventId` / `lastSequence` for reconnect dedupe

Reducer invariants to enforce:
- One active run at a time for Phase 04.
- No duplicate `toolCallId` entries; updates merge into existing item.
- Terminal run phases (`succeeded`, `failed`) ignore non-terminal regressions.

### Anti-Patterns to Avoid
- **Polling-only first implementation:** misses "as run progresses" intent and creates laggy timelines.
- **Unstructured event payloads:** impossible to render stable states when fields vary by event.
- **Client-trusted timing only:** browser clock skew and tab throttling cause misleading durations.
- **Tool-name free text:** breaks requirement to clearly track exactly two tools.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Realtime transport for one-way progress | Custom long-poll protocol | SSE (`EventSource` + `text/event-stream`) | Native browser support, less infra complexity |
| Payload validation | Ad-hoc `typeof` checks everywhere | Zod schemas in shared contract module | Centralized validation and typed inference |
| Run transition logic | Scattered `if` statements in UI handlers | Single reducer/state machine | Prevents invalid transitions and regressions |
| Duration canonicalization | Client-side timer only | Backend-issued timing + client fallback display | Accurate observability and log correlation |

**Key insight:** Phase 04 is mostly a contract-and-state correctness problem; leverage standards (SSE) and schema-first validation instead of inventing transport/state conventions.

## Common Pitfalls

### Pitfall 1: Event ordering/race issues
**What goes wrong:** Tool completion arrives before tool start in UI due to reconnect/replay or async buffering.  
**Why it happens:** No sequence number or idempotent merge strategy.  
**How to avoid:** Include `id`/`sequence` in events and reducer-level dedupe/order guards.  
**Warning signs:** Negative durations, repeated rows, status flapping.

### Pitfall 2: Missing terminal synchronization
**What goes wrong:** Timeline shows running tool forever after backend finished.  
**Why it happens:** No explicit `run_complete`/`run_error` event or stream close handling.  
**How to avoid:** Require terminal event + fallback run-status fetch on stream close.  
**Warning signs:** Run phase stuck in `running` with closed connection.

### Pitfall 3: Schema drift between backend and UI
**What goes wrong:** Frontend silently fails parsing event payloads after backend changes.  
**Why it happens:** Contracts not versioned/validated at runtime.  
**How to avoid:** Parse every envelope/event with Zod; surface parse failures in UI + logs.  
**Warning signs:** Blank timeline despite backend activity.

### Pitfall 4: SSE lifecycle mishandling
**What goes wrong:** Leaked connections or duplicate event listeners across reruns.  
**Why it happens:** EventSource not closed on terminal/error/new run.  
**How to avoid:** Always call `close()` on terminal states and before starting a new run.  
**Warning signs:** Duplicate tool rows or exponential UI updates.

## Code Examples

Verified patterns from official sources:

### SSE event format for named events
```text
// Source: MDN "Using server-sent events"
event: tool_call
id: 12
data: {"runId":"r1","toolCallId":"t1","toolName":"web_search","status":"started","startedAt":1710000000}

```

### FastAPI streaming response for event stream
```python
# Source: FastAPI StreamingResponse docs
from fastapi.responses import StreamingResponse

async def event_generator():
    yield "event: run_state\ndata: {\"state\":\"running\"}\n\n"

@app.get("/api/runs/{run_id}/events")
async def run_events(run_id: str):
    return StreamingResponse(event_generator(), media_type="text/event-stream")
```

### LangGraph custom/updates streaming
```python
# Source: LangGraph streaming docs
for chunk in graph.stream(inputs, stream_mode=["updates", "custom"], version="v2"):
    if chunk["type"] == "updates":
        ...
    elif chunk["type"] == "custom":
        ...
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Batch-only response (wait for final output) | Incremental agent/tool event streaming | Current LangGraph streaming guidance | Better trust/debuggability and perceived responsiveness |
| Ad-hoc stream tuple formats | Unified StreamPart (`type`, `ns`, `data`) with `version="v2"` | LangGraph `>=1.1` | Easier event mapping and typed frontend handlers |
| Generic realtime transport by default | SSE-first for one-way progress feeds | Established web platform usage | Lower complexity for local and phased delivery |

**Deprecated/outdated:**
- Treating agent execution as opaque final-answer-only response for UX/debug workflows.

## Testing Strategy

Plan these test layers in Phase 04:

1. **Reducer unit tests (HIGH priority)**
   - Transition validity (`idle -> starting -> running -> terminal`)
   - Out-of-order event handling and dedupe by `toolCallId`/sequence
   - Duration rendering rules (`in-flight` vs final)

2. **API client contract tests (HIGH priority)**
   - `POST /api/runs` request/response schema parsing
   - SSE message parsing for each named event
   - Stream error and reconnect behavior

3. **Backend/frontend contract integration tests (MEDIUM priority)**
   - Simulated run emits `run_state` + `tool_call` + terminal event
   - UI reaches expected terminal state and shows 2-tool activity clearly

4. **E2E smoke in Docker (MEDIUM priority)**
   - Enter prompt, click run, observe timeline progress and final answer
   - Verify at least one `web_search`/`web_crawl` entry is visible with duration

## Risks

- **Phase 3 contract mismatch:** If Phase 3 exposes only blocking response, Phase 04 timeline cannot be realtime; must add stream endpoint first.
- **SSE reliability in local proxies:** Docker/network buffering may delay events; require keepalive/comments and flush-friendly server behavior.
- **Observability scope overlap:** Full tool input/output belongs to Phase 5; Phase 04 should show status/duration and minimal preview only.
- **Concurrency creep:** Supporting multiple simultaneous runs in UI adds complexity; explicitly keep one-active-run model for this phase.

## Rollout Order

1. **04-01 Minimal prompt/run UI and API wiring**
   - Add run contracts (request + start response + base event schemas)
   - Implement prompt form + run button + top-level run state indicator
   - Implement start-run API call and initial state transitions

2. **04-02 Per-tool timeline with status/duration**
   - Implement SSE subscription and event-to-state reducer updates
   - Render ordered tool timeline rows with status badges and durations
   - Handle terminal run completion/error and cleanup connection lifecycle

3. **Hardening pass before Phase 5**
   - Add ordering/dedupe guards
   - Add integration smoke test for end-to-end event rendering
   - Add explicit placeholders for Phase 5 deep I/O details

## Open Questions

1. **Exact Phase 3 run endpoint shape**
   - What we know: Phase 3 promises frontend-callable execution endpoint and stable metadata.
   - What's unclear: Whether it is blocking-only or already stream-capable.
   - Recommendation: Treat stream endpoint as required Phase 4 dependency; if absent, add as first task in 04-01.

2. **Run history persistence boundary**
   - What we know: Rich run history is Phase 5.
   - What's unclear: Whether Phase 4 should persist latest run across refresh.
   - Recommendation: Keep Phase 4 in-memory only; persist/history belongs to Phase 5.

## Sources

### Primary (HIGH confidence)
- [MDN EventSource](https://developer.mozilla.org/en-US/docs/Web/API/EventSource) - SSE API behavior, lifecycle, and support baseline.
- [MDN Using server-sent events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events) - event format (`event`, `data`, `id`, `retry`), reconnect behavior, connection limits.
- [FastAPI StreamingResponse](https://fastapi.tiangolo.com/advanced/custom-response/#streamingresponse) - authoritative Python streaming response implementation.
- [LangGraph Streaming Docs](https://docs.langchain.com/oss/python/langgraph/streaming) - stream modes, v2 format, custom event emission.
- [Vite Guide](https://vite.dev/guide/) and [Vite server proxy docs](https://vite.dev/config/server-options#server-proxy) - if frontend bundling/dev proxy is introduced.

### Secondary (MEDIUM confidence)
- Existing repository contracts and tests in `src/frontend/contracts.ts` and `src/tests/frontend-api/routes.contracts.test.ts` validating schema-first API envelope patterns.

### Tertiary (LOW confidence)
- WebSearch ecosystem summaries comparing SSE/WebSocket trends (used only to guide direction; all critical claims verified against official docs above).

## Metadata

**Confidence breakdown:**
- Standard stack: **HIGH** - based on official docs + existing repo dependencies.
- Architecture: **HIGH** - aligns with official SSE/LangGraph streaming models and current project constraints.
- Pitfalls: **HIGH** - based on protocol semantics and common event-driven UI failure modes.

**Research date:** 2026-03-17  
**Valid until:** 2026-04-16 (30 days)

