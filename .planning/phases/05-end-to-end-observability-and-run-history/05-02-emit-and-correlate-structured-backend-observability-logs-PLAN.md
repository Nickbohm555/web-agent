---
phase: 05-end-to-end-observability-and-run-history
plan: 02
type: execute
wave: 2
depends_on:
  - "05-01"
files_modified:
  - src/core/telemetry/run-context.ts
  - src/core/telemetry/observability-logger.ts
  - src/frontend/server.ts
  - src/frontend/routes/search.ts
  - src/frontend/routes/fetch.ts
  - docker-compose.yml
  - src/tests/frontend-api/observability-correlation.test.ts
autonomous: true
must_haves:
  truths:
    - "Backend emits structured JSON observability events visible through Docker logs."
    - "Every backend observability event includes run correlation keys (`run_id`, `event_seq`) that match frontend timeline events."
    - "Logs and emitted payloads enforce secret redaction and bounded payload size."
  artifacts:
    - path: "src/core/telemetry/run-context.ts"
      provides: "Run-scoped context storage with run ID and monotonic sequence generator."
    - path: "src/core/telemetry/observability-logger.ts"
      provides: "Structured event logger with redaction/truncation policy and event-type helpers."
    - path: "docker-compose.yml"
      provides: "Docker log driver and rotation config for backend log retrieval via docker compose logs."
    - path: "src/tests/frontend-api/observability-correlation.test.ts"
      provides: "Automated parity checks between UI events and backend log events."
  key_links:
    - from: "src/frontend/server.ts"
      to: "src/core/telemetry/run-context.ts"
      via: "run boundary wrapper initializes run_id and sequence"
      pattern: "withRunContext\\("
    - from: "src/frontend/routes/search.ts"
      to: "src/core/telemetry/observability-logger.ts"
      via: "tool lifecycle emission"
      pattern: "tool_call_(started|succeeded|failed)"
    - from: "src/frontend/routes/fetch.ts"
      to: "src/core/telemetry/observability-logger.ts"
      via: "tool lifecycle emission"
      pattern: "tool_call_(started|succeeded|failed)"
---

<objective>
Emit correlated structured backend observability logs and guarantee parity with frontend tool-event traces.

Purpose: Delivers `OBS-03` and correlation foundation for cohesive run-history debugging in the final slice.
Output: Run context propagation, structured event logger, Docker log retrieval configuration, and correlation parity tests.
</objective>

<execution_context>
@~/.cursor/get-shit-done/workflows/execute-plan.md
@~/.cursor/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/REQUIREMENTS.md
@.planning/phases/05-end-to-end-observability-and-run-history/05-RESEARCH.md
@.planning/phases/05-end-to-end-observability-and-run-history/05-01-SUMMARY.md
@src/frontend/server.ts
@src/frontend/routes/search.ts
@src/frontend/routes/fetch.ts
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add run context and monotonic sequencing for correlation</name>
  <files>src/core/telemetry/run-context.ts, src/frontend/server.ts</files>
  <action>Implement a run-scoped context utility (AsyncLocalStorage) that initializes `run_id` and owns monotonic `event_seq` generation for each run execution boundary. Wire run initialization at the request entrypoint that triggers agent/tool execution so all downstream emissions inherit correlation metadata automatically. Do not hand-thread run IDs through unrelated function signatures when context can provide them.</action>
  <verify>Run `npm run test -- src/tests/frontend-api/observability-correlation.test.ts` and confirm emitted events for a single run have non-empty `run_id`, strictly increasing `event_seq`, and no duplicate (`run_id`, `event_seq`) pairs.</verify>
  <done>All run lifecycle and tool events have deterministic correlation keys without manual parameter plumbing.</done>
</task>

<task type="auto">
  <name>Task 2: Emit structured lifecycle/tool logs with redaction and truncation</name>
  <files>src/core/telemetry/observability-logger.ts, src/frontend/routes/search.ts, src/frontend/routes/fetch.ts</files>
  <action>Create an observability logger helper that emits JSON events aligned to the Phase 05 RunEvent contract (`run_started`, `tool_call_started`, `tool_call_succeeded`, `tool_call_failed`, `final_answer_generated`, `run_completed`, `run_failed`). Apply redaction policy for known sensitive keys and payload truncation policy for large objects before emission. Instrument both search and fetch routes to log tool-start, tool-success, and tool-failure events using shared helper APIs.</action>
  <verify>Run `npm run test -- src/tests/frontend-api/observability-correlation.test.ts` and confirm logs for success/failure paths include expected event types, preserve correlation fields, and never expose raw sensitive values.</verify>
  <done>Backend emits structured, safe, correlation-ready tool events for both search and fetch paths.</done>
</task>

<task type="auto">
  <name>Task 3: Wire Docker log retrieval and enforce UI-log parity checks</name>
  <files>docker-compose.yml, src/tests/frontend-api/observability-correlation.test.ts</files>
  <action>Update `docker-compose.yml` backend logging configuration to use JSON logs with timestamp visibility and rotation bounds appropriate for local debugging. Add verification tests/assertions that compare frontend tool timeline events against backend structured log events for the same run, matching on (`run_id`, `event_seq`, `event_type`) parity.</action>
  <verify>Run `docker compose up -d backend` then `docker compose logs --timestamps backend`; confirm structured JSON events include correlation keys. Run `npm run test -- src/tests/frontend-api/observability-correlation.test.ts` and confirm parity assertions pass.</verify>
  <done>User can inspect structured backend logs via Docker and correlate each frontend tool event to exactly one backend log record.</done>
</task>

</tasks>

<verification>
Run `npm run typecheck`, `npm run test -- src/tests/frontend-api/observability-correlation.test.ts`, and `docker compose logs --timestamps backend`. Confirm correlation parity and redaction invariants hold for at least one successful and one failed tool call.
</verification>

<success_criteria>
- Backend logs expose structured events retrievable from Docker logs with timestamps.
- Correlation keys (`run_id`, `event_seq`) are present and consistent across UI and backend logs.
- Secret redaction and payload truncation are enforced before log emission.
</success_criteria>

<output>
After completion, create `.planning/phases/05-end-to-end-observability-and-run-history/05-02-SUMMARY.md`
</output>
