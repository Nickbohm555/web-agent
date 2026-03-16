---
phase: 05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly
plan: 03
type: execute
wave: 3
depends_on: ["05-02"]
files_modified:
  - public/app.js
  - public/index.html
  - src/tests/frontend-api/routes.contracts.test.ts
  - src/tests/frontend-ui/dev-console.smoke.test.ts
autonomous: true
must_haves:
  truths:
    - "A user can run both operations from one action and see distinct outputs for each function call."
    - "Recent calls remain visible for quick comparison/replay while validating behavior."
    - "Frontend + API wiring is covered by executable verification so regressions are caught early."
  artifacts:
    - path: "public/app.js"
      provides: "Run-both orchestration and in-memory call history/replay behavior"
    - path: "public/index.html"
      provides: "Run-both control and history list surface"
    - path: "src/tests/frontend-ui/dev-console.smoke.test.ts"
      provides: "Automated smoke checks for visible invocation/output flow"
    - path: "src/tests/frontend-api/routes.contracts.test.ts"
      provides: "Expanded backend contract assertions used by frontend flow"
  key_links:
    - from: "public/app.js"
      to: "/api/search"
      via: "run-both sequence step one"
      pattern: "runBoth|/api/search"
    - from: "public/app.js"
      to: "/api/fetch"
      via: "run-both sequence step two and standalone run"
      pattern: "runBoth|/api/fetch"
    - from: "src/tests/frontend-ui/dev-console.smoke.test.ts"
      to: "public/index.html"
      via: "smoke verification of operation controls and output visibility"
      pattern: "Run Both|search|fetch"
---

<objective>
Finish Phase 05 by adding combined execution flow, call history visibility, and hard verification that the frontend reliably demonstrates both SDK primitives.

Purpose: Ensure the validation surface is not just interactive but also repeatable and trustworthy for future debugging and demo use.
Output: Run-both orchestration, recent-call history/replay, and automated smoke tests for frontend/API behavior.
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
@.planning/phases/05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly/05-02-SUMMARY.md
@AGENTS.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add run-both orchestration with explicit per-call outputs</name>
  <files>public/app.js, public/index.html</files>
  <action>Implement a `Run Both` action that executes search then fetch in a deterministic sequence (search first, fetch second) while preserving individual state/output panes so users can still see each function call independently. If search returns no usable URL for follow-up fetch, surface an explicit non-crashing warning in the fetch section.</action>
  <verify>Manual browser test confirms one click triggers both operations and leaves separate visible outputs for each call.</verify>
  <done>The frontend provides a single-action flow that still keeps search/fetch outputs clearly separated.</done>
</task>

<task type="auto">
  <name>Task 2: Implement recent call history and replay controls</name>
  <files>public/app.js, public/index.html</files>
  <action>Add in-memory history (bounded to a small recent count) that records operation name, status, duration, timestamp, request payload, and response/error envelope. Provide replay controls that repopulate inputs and re-run the selected call, keeping this history local-memory only (no disk persistence or secret storage).</action>
  <verify>Manual verification shows new entries after each run and successful replay from at least one search and one fetch history item.</verify>
  <done>Users can compare recent calls and rerun scenarios without retyping payloads.</done>
</task>

<task type="auto">
  <name>Task 3: Add smoke verification for full frontend validation flow</name>
  <files>src/tests/frontend-api/routes.contracts.test.ts, src/tests/frontend-ui/dev-console.smoke.test.ts</files>
  <action>Extend backend route tests for run-both assumptions and add a frontend smoke test that verifies the page can trigger search/fetch actions and render clear output/error states. If no browser E2E harness exists yet, implement the smoke test with the lightest viable approach used in this repo and keep it deterministic for CI execution.</action>
  <verify>`npm run test -- src/tests/frontend-api/routes.contracts.test.ts src/tests/frontend-ui/dev-console.smoke.test.ts` passes, then `npm run typecheck && npm run build` pass.</verify>
  <done>Phase 05 behavior is protected by executable verification that covers visible invocation/output requirements.</done>
</task>

</tasks>

<verification>
Run end-of-phase gates in order: `npm install`, `npm run typecheck`, `npm run test`, `npm run build`.
</verification>

<success_criteria>
- The frontend offers independent search/fetch actions plus a deterministic run-both action.
- Output remains clear and operation-specific, with request/response/timing/error visibility.
- Recent call history and replay improve debugging without violating safety/secret constraints.
- Automated tests validate both route contract behavior and UI smoke-level invocation/output flows.
</success_criteria>

<output>
After completion, create `.planning/phases/05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly/05-03-SUMMARY.md`
</output>
