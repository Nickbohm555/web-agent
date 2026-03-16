---
phase: 05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly
plan: 02
type: execute
wave: 2
depends_on: ["05-01"]
files_modified:
  - public/index.html
  - public/styles.css
  - public/app.js
autonomous: true
must_haves:
  truths:
    - "A user can trigger search and fetch independently from the frontend and clearly see each call state."
    - "The frontend displays exactly what was sent and what was returned, including duration and status."
    - "Failure states are understandable, with explicit error code/message/details instead of generic text."
  artifacts:
    - path: "public/index.html"
      provides: "UI forms and result regions for both operations"
    - path: "public/app.js"
      provides: "Client-side request state management and API invocation wiring"
    - path: "public/styles.css"
      provides: "Readable visual layout for request/response visibility"
  key_links:
    - from: "public/app.js"
      to: "/api/search"
      via: "search submit flow using POST JSON request"
      pattern: "fetch\\(\"/api/search\""
    - from: "public/app.js"
      to: "/api/fetch"
      via: "fetch submit flow using POST JSON request"
      pattern: "fetch\\(\"/api/fetch\""
    - from: "public/index.html"
      to: "public/app.js"
      via: "event-driven form actions and output pane binding"
      pattern: "id=|data-"
---

<objective>
Build the frontend validation surface so a user can invoke `search(...)` and `fetch(...)` and inspect output clearly from one local page.

Purpose: Deliver the visible proof that both primitives work end-to-end while keeping the UI focused on transparent debugging rather than production polish.
Output: A static dev console page with two operation panels, explicit run states, and structured request/response display.
</objective>

<execution_context>
@~/.cursor/get-shit-done/workflows/execute-plan.md
@~/.cursor/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/REQUIREMENTS.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly/05-RESEARCH.md
@.planning/phases/05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly/05-01-SUMMARY.md
@AGENTS.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Build dual-operation console layout</name>
  <files>public/index.html, public/styles.css</files>
  <action>Create a clear two-panel UI: one section for search, one for fetch, each with inputs, submit button, running/status indicators, and dedicated request/response regions. Include obvious labels for operation, status code, duration, and timestamp so users can immediately distinguish which function ran and what it returned.</action>
  <verify>Start frontend server and visually confirm both panels render with distinct controls and output zones.</verify>
  <done>UI structure exists for independent invocation and output inspection of both operations.</done>
</task>

<task type="auto">
  <name>Task 2: Wire client invocation and state transitions</name>
  <files>public/app.js</files>
  <action>Implement explicit per-operation state machines (`idle`, `running`, `success`, `error`) and form submit handlers that POST JSON payloads to `/api/search` and `/api/fetch`. Capture and render request payload, response envelope, duration, and error details; disable repeated submits while requests are in flight to reduce accidental rate-limit bursts.</action>
  <verify>Manual run from the browser confirms each button triggers the matching API route and updates state/output correctly.</verify>
  <done>Search and fetch can both be invoked from the frontend with clear state and result visibility.</done>
</task>

<task type="auto">
  <name>Task 3: Harden output readability for debugging workflows</name>
  <files>public/app.js, public/styles.css</files>
  <action>Add structured rendering helpers that separate metadata from payload, provide pretty-printed JSON by default, and show typed error blocks (`code`, `message`, `details`). Keep output complete enough for troubleshooting while avoiding hidden fields or truncated operation context.</action>
  <verify>Manual tests for success and failure responses show readable, complete output sections without ambiguity.</verify>
  <done>A user can quickly understand what was sent, what returned, and why a call failed.</done>
</task>

</tasks>

<verification>
Run the frontend server and execute one successful + one failing call for both operations, then run `npm run typecheck` and `npm run build`.
</verification>

<success_criteria>
- The frontend can independently invoke both `search` and `fetch`.
- Each operation displays request payload, response envelope, duration, and status in a clearly separated view.
- Error output is typed and actionable, including validation/safety/compliance failures.
</success_criteria>

<output>
After completion, create `.planning/phases/05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly/05-02-SUMMARY.md`
</output>
