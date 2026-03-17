# Phase 05: End-to-End Observability and Run History - Research

**Researched:** 2026-03-17
**Domain:** Full-stack observability for tool I/O, event correlation, and run history
**Confidence:** HIGH

## Summary

Phase 05 should be planned as an observability-contract phase, not a UI-polish phase. The critical deliverable is one stable event model that powers both frontend rendering and backend logs, with a single correlation key (`run_id`) and monotonic event ordering (`event_seq`). Without that shared contract, success criteria 1-4 fragment into separate implementations that drift and become hard to debug.

Given the current stack (Node/TypeScript, Express, Pino, Docker logs), the standard approach is: emit structured JSON events to stdout, include run-scoped context automatically via async context propagation, and render the same event payloads in the frontend timeline with full request/response payload visibility. Keep payload storage bounded in memory for v1 local debugging flow, and explicitly redact secrets at logger boundary.

The practical planning sequence is: first establish event schema and UI payload rendering primitives, then wire backend structured logs with guaranteed correlation fields, then consolidate into a run-history flow where final answer and tool trace are co-located and replayable.

**Primary recommendation:** Define and enforce a canonical `RunEvent` contract (`run_id`, `event_seq`, `event_type`, `tool_name`, `tool_input`, `tool_output`, `final_answer`) before implementing UI or log plumbing.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `pino` | `^10.3.1` (repo) | Structured JSON logging | Fast JSON logs to stdout; supports child loggers and redaction for safe observability |
| `node:async_hooks` (`AsyncLocalStorage`) | Node stable API | Request/run-scoped context propagation | Official Node mechanism for async context correlation without parameter threading |
| `express` | `^5.2.1` (repo) | API boundary and middleware wiring | Natural place to initialize run context and attach request metadata |
| Docker `json-file` logging driver | Engine default | Container stdout/stderr retention for `docker logs` | Officially supported local log capture path with timestamped records |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `zod` | `^4.3.6` (repo) | Runtime validation for event envelopes | Validate frontend/backend event schema parity |
| `crypto.randomUUID()` (Node built-in) | Node built-in | Run ID generation | Generate collision-safe correlation IDs for each run |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Pino + stdout JSON | OpenTelemetry full tracing stack | Better distributed tracing, but excessive integration cost for current local single-backend phase |
| AsyncLocalStorage | Manual `runId` plumbing through function args | Simpler to reason about in tiny code, but brittle and noisy as call graph grows |
| In-memory run history | Persistent DB-backed history | Better long-term retention, but unnecessary complexity for current local debugging requirement |

**Installation:**
```bash
npm install pino zod express
```

## Architecture Patterns

### Recommended Project Structure
```
src/
├── observability/          # Shared run/event schemas, context, logger helpers
├── frontend/               # API + UI rendering for run history and payload views
├── sdk/                    # Tool invocation boundary (search/fetch wrappers)
└── tests/                  # Contract, correlation, and end-to-end observability tests
```

### Pattern 1: Canonical Run Event Envelope
**What:** One typed event schema reused by frontend state and backend logs.
**When to use:** Every agent/tool lifecycle emission (run start, tool start/end, final answer, run end, run error).
**Example:**
```typescript
// Source: project contract pattern + Zod docs (https://zod.dev/)
const RunEventSchema = z.object({
  run_id: z.string().min(1),
  event_seq: z.number().int().nonnegative(),
  ts: z.string().datetime(),
  event_type: z.enum([
    "run_started",
    "tool_call_started",
    "tool_call_succeeded",
    "tool_call_failed",
    "final_answer_generated",
    "run_completed",
    "run_failed",
  ]),
  tool_name: z.string().optional(),
  payload: z.unknown().optional(),
});
```

### Pattern 2: Async Context Correlation
**What:** Set `run_id` once at request/run boundary using `AsyncLocalStorage`, then read it anywhere for logs/events.
**When to use:** All asynchronous tool execution paths where correlation must be automatic.
**Example:**
```typescript
// Source: Node AsyncLocalStorage docs (https://nodejs.org/api/async_context.html)
import { AsyncLocalStorage } from "node:async_hooks";
const runContext = new AsyncLocalStorage<{ runId: string; seq: number }>();

export function withRunContext<T>(runId: string, fn: () => Promise<T>) {
  return runContext.run({ runId, seq: 0 }, fn);
}
```

### Pattern 3: Pino Child Logger Per Run
**What:** Create run-scoped child logger with stable bindings (`run_id`, `component`), emit structured event records.
**When to use:** Any event that must correlate with UI timeline and Docker logs.
**Example:**
```typescript
// Source: Pino child logger docs (https://raw.githubusercontent.com/pinojs/pino/main/docs/child-loggers.md)
const base = pino({
  level: process.env.LOG_LEVEL ?? "info",
  redact: {
    paths: ["payload.apiKey", "payload.headers.authorization"],
    censor: "[Redacted]",
  },
});

const log = base.child({ run_id: runId, component: "agent" });
log.info({ event_type: "tool_call_started", tool_name: "web_search", event_seq: 3, payload: toolInput });
```

### Pattern 4: Frontend Timeline + Payload Inspector Split
**What:** Use two coordinated views: timeline list for event flow, detail pane for full tool I/O payload.
**When to use:** Any debugging UI where users need both chronology and full JSON data.
**Example:**
```typescript
// Source: established debugging UI pattern (internal recommendation)
// timeline selection key: `${run_id}:${event_seq}`
// detail view renders JSON.stringify(event.payload, null, 2)
```

### Anti-Patterns to Avoid
- **Dual event models:** separate frontend and backend event shapes cause drift and impossible correlation bugs.
- **Ad-hoc correlation fields:** mixing `requestId`, `traceId`, `runId` without canonical naming breaks filtering.
- **Unbounded payload retention:** full payload history without limits can explode memory during long sessions.
- **Raw-secret logging:** emitting headers/env/tool secrets to logs violates operational safety.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Async request/run context propagation | Custom global maps keyed by promise IDs | `AsyncLocalStorage` | Official, stable, and safer than manual async bookkeeping |
| Log redaction engine | Custom recursive key-scrubber | Pino `redact` | Covers nested paths/wildcards with known performance behavior |
| Container log capture | Custom file appenders in app code | stdout + Docker logging driver | Native container logging path; aligns with `docker logs` tooling |
| Schema enforcement for event payloads | Handwritten type guards only | Zod runtime schemas | Catch shape regressions at runtime and in tests |

**Key insight:** Observability failures usually come from glue code and drift, not missing features. Reuse built-in primitives for correlation and log transport.

## Common Pitfalls

### Pitfall 1: Event Ordering Drift
**What goes wrong:** UI shows tool events out of order relative to backend logs.
**Why it happens:** relying only on timestamps from different emit points/clock precision.
**How to avoid:** maintain per-run monotonic `event_seq` incremented at event emission boundary.
**Warning signs:** same run has duplicate or skipped sequence numbers.

### Pitfall 2: Correlation Gaps Across Async Boundaries
**What goes wrong:** some logs/events miss `run_id`.
**Why it happens:** context not initialized at run entry or lost in detached async callbacks.
**How to avoid:** enforce `withRunContext()` wrapper for all run entrypoints; test every emitted event has `run_id`.
**Warning signs:** `docker logs | jq 'select(.run_id==null)'` returns events.

### Pitfall 3: Sensitive Payload Exposure
**What goes wrong:** API keys/auth headers/tool credentials appear in logs/UI payload viewer.
**Why it happens:** full payload observability implemented before redaction policy.
**How to avoid:** define allowlist/redaction list before enabling payload rendering/logging.
**Warning signs:** secrets visible in local logs during manual run.

### Pitfall 4: UI-Only History Without Backend Parity
**What goes wrong:** frontend history exists but cannot be validated against backend logs.
**Why it happens:** no shared event IDs or sequence/correlation fields.
**How to avoid:** include `run_id` and `event_seq` in both API event stream/history and backend log entries.
**Warning signs:** impossible to map a UI timeline event to one log line.

### Pitfall 5: Memory Blow-Up from Full Payload History
**What goes wrong:** long local sessions degrade frontend/backend performance.
**Why it happens:** storing unlimited full I/O payloads per run in memory.
**How to avoid:** bounded ring buffer per run + max runs retained + payload-size guard.
**Warning signs:** browser tab memory grows continuously with repeated runs.

## Code Examples

Verified patterns from official sources:

### Structured JSON Logs via Docker
```yaml
# Source: Docker Compose logging reference + json-file driver docs
services:
  backend:
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
```

### Run Context Initialization at Request Boundary
```typescript
// Source: Node AsyncLocalStorage docs
app.post("/api/run", async (req, res) => {
  const runId = crypto.randomUUID();
  await withRunContext(runId, async () => {
    // All downstream logs/events can include runId from context
    res.json(await executeRun(req.body));
  });
});
```

### Safe Pino Redaction for Full Payload Logging
```typescript
// Source: Pino redaction docs
const logger = pino({
  redact: {
    paths: [
      "payload.headers.authorization",
      "payload.apiKey",
      "payload.token",
    ],
    censor: "[Redacted]",
  },
});
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Ad-hoc `console.log` strings | Structured JSON logs with fixed event fields | Matured across Node logging ecosystem | Machine-filterable logs and deterministic correlation |
| Passing request IDs manually through function args | Async context propagation (`AsyncLocalStorage`) | Became stable in Node v16+ | Lower coupling and fewer missed correlation fields |
| Separate UI state models and backend logs | Shared event contract for UI + logs | Current observability best practice | Eliminates drift and enables exact run replay/debug |

**Deprecated/outdated:**
- Manual log file scraping from Docker container filesystem: Docker docs warn log files are daemon-managed and should not be externally manipulated.

## Suggested Plan Slices (Executable Guidance)

### Slice 05-01: Full Tool Payload Rendering in UI
- Define `RunEventSchema` and `ToolPayloadSchema` in shared frontend/backend contract.
- Implement timeline list + payload inspector pane with pretty JSON and expandable sections.
- Add payload guardrails: truncation threshold, explicit "truncated" marker, secret-redacted view.
- Verification:
  - Success path: both tool input and output payloads visible for one run.
  - Error path: failed tool call still captures full input + structured error output.
  - Contract test: every rendered event validates against schema.

### Slice 05-02: Structured Backend Observability + Correlation
- Add run-context middleware/wrapper (`run_id` + `event_seq`) around run execution.
- Create run-scoped child logger and emit lifecycle events (`tool_call_started`, `tool_call_succeeded`, etc.).
- Enforce logger redaction config and log-size discipline.
- Wire Docker Compose logging options (`json-file`, rotation).
- Verification:
  - `docker compose logs --timestamps backend` shows JSON events with `run_id` and `event_seq`.
  - For a single run, every tool event in UI has matching backend log event by (`run_id`, `event_seq`, `event_type`).
  - No secrets in logs under known sensitive keys.

### Slice 05-03: Cohesive Run History (Final Answer + Tool Trace)
- Build bounded in-memory run history store containing final answer + ordered event list.
- UI flow: select run -> see final answer + timeline + payload detail in one screen.
- Add replay/inspect controls without reissuing backend calls unless explicitly requested.
- Verification:
  - User can open prior run and view final answer plus complete tool trace.
  - Ordering invariant holds (`event_seq` strictly increasing per run).
  - History bounds enforced (max runs, max events/run, max payload bytes/event).

## Practical Tradeoffs and Risk Controls

- **Payload completeness vs safety:** full payload visibility helps debugging but raises leak risk; enforce redaction + truncation as non-optional acceptance criteria.
- **In-memory simplicity vs durability:** in-memory history is fastest for v1 but volatile on restart; acceptable for local debugging phase if explicitly documented.
- **Single-schema rigor vs speed:** schema-first adds up-front work but prevents UI/log drift and reduces phase rework.
- **Verbose logging vs runtime overhead:** event-rich logs increase I/O; keep level controls and payload caps to avoid noisy/unusable logs.

## Verification Criteria for Planner

- **Contract invariants**
  - Every emitted event validates against `RunEventSchema`.
  - Required correlation fields (`run_id`, `event_seq`, `event_type`, `ts`) always present.
- **Correlation invariants**
  - For each UI timeline event, exactly one matching backend log event exists for the same run.
  - No duplicate (`run_id`, `event_seq`) pairs.
- **Observability invariants**
  - Tool input and output payloads visible in UI for both success and failure paths.
  - Final answer is displayed alongside full ordered tool trace in run history view.
- **Safety invariants**
  - Redaction tests prove configured sensitive keys never appear in logs/UI payload inspector.
  - Docker logs are retrievable with timestamps and remain bounded via rotation config.

## Open Questions

1. **Backend execution path authority for Phase 05**
   - What we know: roadmap references Python LangGraph flow; repository currently executes TypeScript `search/fetch` routes.
   - What's unclear: whether Phase 05 should instrument TS backend, Python backend, or both during transition.
   - Recommendation: lock this in plan preamble; otherwise correlation contracts may be duplicated.

2. **Frontend technology target for run history UI**
   - What we know: current frontend is Express API/server shell; no committed static UI files in repo currently.
   - What's unclear: whether UI is vanilla TS, framework-based, or generated separately.
   - Recommendation: keep plan framework-agnostic and require behavior-level acceptance tests.

## Sources

### Primary (HIGH confidence)
- Node.js docs: https://nodejs.org/api/async_context.html - `AsyncLocalStorage` stability and usage.
- Docker docs: https://docs.docker.com/engine/logging/drivers/json-file/ - default JSON logging behavior and rotation options.
- Docker docs: https://docs.docker.com/reference/cli/docker/compose/logs/ - Compose log retrieval and timestamp options.
- Docker docs: https://docs.docker.com/reference/cli/docker/container/logs/ - `docker logs` timestamp/details semantics.
- Pino official docs: https://raw.githubusercontent.com/pinojs/pino/main/docs/redaction.md - redaction API and safety caveats.
- Pino official docs: https://raw.githubusercontent.com/pinojs/pino/main/docs/child-loggers.md - child logger behavior and caveats.
- Pino API docs: https://raw.githubusercontent.com/pinojs/pino/main/docs/api.md - `redact`, `mixin`, level/options references.

### Secondary (MEDIUM confidence)
- Internal repository contracts and tests (`src/frontend/contracts.ts`, `src/tests/frontend-api/routes.contracts.test.ts`) for current envelope shape and metadata expectations.

### Tertiary (LOW confidence)
- Community WebSearch results for 2026 observability discussions; used only for discovery, then validated against official docs above.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - directly supported by current repo dependencies and official docs.
- Architecture: HIGH - based on official primitives (`AsyncLocalStorage`, Pino child/redaction) plus repo-compatible contract design.
- Pitfalls: MEDIUM - validated by common failure modes and current codebase constraints; still environment-sensitive.

**Research date:** 2026-03-17
**Valid until:** 2026-04-16
