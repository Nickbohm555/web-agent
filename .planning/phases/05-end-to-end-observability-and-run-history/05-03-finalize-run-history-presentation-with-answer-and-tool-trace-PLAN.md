---
phase: 05-end-to-end-observability-and-run-history
plan: 03
type: execute
wave: 3
depends_on:
  - "05-01"
  - "05-02"
files_modified:
  - src/frontend/run-history/store.ts
  - src/frontend/routes/run-history.ts
  - src/frontend/server.ts
  - public/index.html
  - public/app.js
  - src/tests/frontend-api/run-history.integration.test.ts
autonomous: true
must_haves:
  truths:
    - "User can open a run and inspect final answer plus full ordered tool trace in one cohesive UI flow."
    - "Run history preserves event ordering and correlation semantics across current and prior runs."
    - "Run history remains bounded so debugging stays responsive during repeated local runs."
  artifacts:
    - path: "src/frontend/run-history/store.ts"
      provides: "Bounded in-memory run history store for final answers and ordered event traces."
      contains: ["maxRuns", "maxEventsPerRun", "maxPayloadBytes", "ordering checks"]
    - path: "src/frontend/routes/run-history.ts"
      provides: "API endpoints to list runs and fetch one run with final answer plus full tool event history."
    - path: "public/app.js"
      provides: "UI flow that unifies run selection, final answer panel, timeline, and payload detail pane."
    - path: "src/tests/frontend-api/run-history.integration.test.ts"
      provides: "Integration tests for answer-plus-trace rendering, ordering invariants, and retention bounds."
  key_links:
    - from: "src/frontend/routes/run-history.ts"
      to: "src/frontend/run-history/store.ts"
      via: "route handlers read/write run snapshots"
      pattern: "getRun\\(|listRuns\\("
    - from: "public/app.js"
      to: "src/frontend/routes/run-history.ts"
      via: "run selection fetches cohesive run payload"
      pattern: "/api/runs/"
    - from: "src/frontend/run-history/store.ts"
      to: "05-02 observability emissions"
      via: "ingest events keyed by run_id and event_seq"
      pattern: "run_id.*event_seq"
---

<objective>
Finalize one debugging surface where each run shows final answer and full tool trace with stable ordering and retention.

Purpose: Delivers `OBS-04` by completing the end-to-end observability loop from prompt run to correlated history inspection.
Output: Bounded run-history storage/API plus a cohesive UI run viewer integrating answer, timeline, and payload details.
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
@.planning/phases/05-end-to-end-observability-and-run-history/05-02-SUMMARY.md
@public/index.html
@public/app.js
</context>

<tasks>

<task type="auto">
  <name>Task 1: Implement bounded run-history store for answer + tool trace</name>
  <files>src/frontend/run-history/store.ts</files>
  <action>Create a run-history storage module keyed by `run_id` that stores final answer text and ordered tool events. Enforce strict event ordering by monotonic `event_seq`, reject or repair out-of-order duplicates deterministically, and enforce retention limits (`maxRuns`, `maxEventsPerRun`, `maxPayloadBytes`) with explicit truncation metadata preserved for UI visibility.</action>
  <verify>Run `npm run test -- src/tests/frontend-api/run-history.integration.test.ts` and confirm ordering invariants, duplicate protection, and retention bound behavior all pass.</verify>
  <done>Run history is deterministic, bounded, and includes everything needed to render answer plus full trace for each run.</done>
</task>

<task type="auto">
  <name>Task 2: Expose run-history API endpoints and integrate into server</name>
  <files>src/frontend/routes/run-history.ts, src/frontend/server.ts</files>
  <action>Add API routes to list available runs and retrieve one run snapshot containing final answer, ordered timeline events, and payload metadata for inspector rendering. Register these routes in the frontend server without breaking existing search/fetch endpoints. Ensure response contracts align with RunEvent schema and correlation keys from prior slices.</action>
  <verify>Run `npm run test -- src/tests/frontend-api/run-history.integration.test.ts` and validate route contracts for list/detail endpoints, including both populated and empty-history states.</verify>
  <done>Backend provides a stable per-run history API returning final answer and full trace in one response flow.</done>
</task>

<task type="auto">
  <name>Task 3: Finalize cohesive UI flow and add end-to-end history tests</name>
  <files>public/index.html, public/app.js, src/tests/frontend-api/run-history.integration.test.ts</files>
  <action>Update the UI so selecting a run shows final answer, ordered timeline, and per-event payload inspector in one screen without requiring separate debugging paths. Add integration tests that assert one cohesive run-view response model and UI behavior-level invariants: answer visibility, complete trace presence, ordering stability, and handling of bounded/truncated history entries.</action>
  <verify>Run `npm run test -- src/tests/frontend-api/run-history.integration.test.ts` and perform one manual run in `npm run dev:frontend` to confirm final answer and tool trace are co-located and navigable for current and prior runs.</verify>
  <done>User can debug a run end-to-end in one cohesive UI flow: final answer plus full per-run tool history.</done>
</task>

</tasks>

<verification>
Run `npm run typecheck` and `npm run test -- src/tests/frontend-api/run-history.integration.test.ts`. Manually verify one run and one historical run show final answer + ordered full tool trace with payload inspection in the same UI flow.
</verification>

<success_criteria>
- Run detail view combines final answer and complete ordered tool history for the same run.
- History API/UI preserve correlation and ordering semantics established in prior slices.
- Retention and payload-size bounds prevent unbounded local memory/log growth.
</success_criteria>

<output>
After completion, create `.planning/phases/05-end-to-end-observability-and-run-history/05-03-SUMMARY.md`
</output>
