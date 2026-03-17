---
phase: 05-end-to-end-observability-and-run-history
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/frontend/contracts/run-events.ts
  - src/frontend/contracts.ts
  - public/index.html
  - public/app.js
  - src/tests/frontend-api/run-events.contracts.test.ts
autonomous: true
must_haves:
  truths:
    - "User can inspect full tool input and output payloads for each tool event in the UI."
    - "Tool failure events still expose tool input and structured error output in the same payload inspector."
    - "Payload rendering is safe: sensitive fields are redacted and oversized payloads are visibly truncated."
  artifacts:
    - path: "src/frontend/contracts/run-events.ts"
      provides: "Canonical RunEvent runtime schema and TypeScript type for tool lifecycle/frontend timeline rendering."
      contains: ["run_id", "event_seq", "event_type", "tool_input", "tool_output", "truncation", "redaction"]
    - path: "public/index.html"
      provides: "Run timeline and payload inspector shell in one debug view."
    - path: "public/app.js"
      provides: "UI behavior that renders event list and selected event payload JSON."
    - path: "src/tests/frontend-api/run-events.contracts.test.ts"
      provides: "Schema and rendering guardrail tests for payload completeness and safety."
  key_links:
    - from: "src/frontend/contracts/run-events.ts"
      to: "public/app.js"
      via: "event validation before render"
      pattern: "RunEventSchema\\.parse"
    - from: "public/app.js"
      to: "public/index.html"
      via: "timeline selection drives payload detail pane"
      pattern: "data-event-key"
    - from: "src/tests/frontend-api/run-events.contracts.test.ts"
      to: "src/frontend/contracts/run-events.ts"
      via: "contract invariant checks"
      pattern: "expect\\(RunEventSchema\\.parse"
---

<objective>
Add full tool payload rendering to the frontend using one canonical run-event contract and visible safety guardrails.

Purpose: Delivers `OBS-02` and establishes the contract foundation required for backend-log correlation in the next slice.
Output: Shared `RunEvent` schema, payload inspector UI, and tests proving schema validity plus redaction/truncation behavior.
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
@src/frontend/contracts.ts
@src/frontend/server.ts
</context>

<tasks>

<task type="auto">
  <name>Task 1: Define canonical RunEvent contract with safety metadata</name>
  <files>src/frontend/contracts/run-events.ts, src/frontend/contracts.ts</files>
  <action>Create `RunEventSchema` and related schemas/types for tool lifecycle events with required fields (`run_id`, `event_seq`, `event_type`, `ts`) and tool payload fields (`tool_input`, `tool_output`, `error_output`). Add explicit safety fields for truncation/redaction so UI can show payload policy decisions, and export parsers/helpers from `src/frontend/contracts.ts`. Keep this contract canonical for both frontend rendering and backend emission; do not create parallel event models.</action>
  <verify>Run `npm run test -- src/tests/frontend-api/run-events.contracts.test.ts` after adding tests in Task 3 and confirm valid events parse while malformed events (missing correlation fields or bad ordering metadata) fail schema validation.</verify>
  <done>Frontend has one importable runtime-validated `RunEvent` contract that includes complete tool payload slots and safety markers.</done>
</task>

<task type="auto">
  <name>Task 2: Implement timeline + payload inspector rendering full tool I/O</name>
  <files>public/index.html, public/app.js</files>
  <action>Build the debugging UI flow where a user selects a run event in a timeline and sees full request/response JSON in a dedicated payload pane. Render both success and failure tool events, include obvious badges/labels for redacted and truncated fields, and preserve deterministic ordering by (`event_seq`). Keep UI framework-agnostic and local-first.</action>
  <verify>Run `npm run dev:frontend`, execute one run that includes at least one tool success and one tool failure path, and confirm the browser shows complete input/output payload sections for both events with visible truncation/redaction indicators when applicable.</verify>
  <done>User can inspect per-tool input and output payloads directly from the timeline UI without switching views.</done>
</task>

<task type="auto">
  <name>Task 3: Add contract and safety regression tests for payload rendering</name>
  <files>src/tests/frontend-api/run-events.contracts.test.ts</files>
  <action>Add focused tests that validate: (1) canonical event schema acceptance/rejection, (2) payload rendering availability for tool success/failure events, and (3) safety invariants for secret redaction and payload truncation markers. Use representative payloads containing known sensitive keys (`authorization`, `apiKey`, `token`) to enforce non-leak behavior.</action>
  <verify>Run `npm run test -- src/tests/frontend-api/run-events.contracts.test.ts` and confirm all new invariants pass.</verify>
  <done>Automated tests prevent regressions that would hide tool payloads, break schema parity, or expose secrets in the inspector.</done>
</task>

</tasks>

<verification>
Run `npm run typecheck` and `npm run test -- src/tests/frontend-api/run-events.contracts.test.ts`. Confirm one frontend run displays ordered events with complete tool payloads and explicit redaction/truncation state for the selected event.
</verification>

<success_criteria>
- Every tool event rendered in UI validates against the canonical `RunEvent` schema.
- The payload inspector shows both tool input and output for success and failure events.
- Sensitive fields are not shown raw, and truncation is explicit rather than silent.
</success_criteria>

<output>
After completion, create `.planning/phases/05-end-to-end-observability-and-run-history/05-01-SUMMARY.md`
</output>
