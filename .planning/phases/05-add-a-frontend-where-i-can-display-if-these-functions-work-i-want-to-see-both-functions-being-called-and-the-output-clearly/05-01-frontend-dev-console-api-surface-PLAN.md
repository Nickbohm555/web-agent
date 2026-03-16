---
phase: 05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - package.json
  - src/frontend/contracts.ts
  - src/frontend/routes/search.ts
  - src/frontend/routes/fetch.ts
  - src/frontend/server.ts
  - src/tests/frontend-api/routes.contracts.test.ts
autonomous: true
must_haves:
  truths:
    - "A local frontend process can invoke server endpoints that call SDK `search(...)` and `fetch(...)` without exposing secrets in the browser."
    - "Each API call returns an explicit envelope with operation name, request payload, duration, and normalized success or typed error output."
    - "Validation and safety/compliance failures are returned as clear, inspectable responses instead of opaque 500s."
  artifacts:
    - path: "src/frontend/contracts.ts"
      provides: "Zod request/response envelopes shared by both frontend routes"
    - path: "src/frontend/routes/search.ts"
      provides: "POST handler that validates payload and calls SDK `search(...)`"
    - path: "src/frontend/routes/fetch.ts"
      provides: "POST handler that validates payload and calls SDK `fetch(...)`"
    - path: "src/frontend/server.ts"
      provides: "Express bootstrap with `/api/search` and `/api/fetch` wiring"
    - path: "src/tests/frontend-api/routes.contracts.test.ts"
      provides: "Route-level tests for validation and envelope shape"
  key_links:
    - from: "src/frontend/routes/search.ts"
      to: "src/sdk/search.ts"
      via: "validated route handler invoking SDK search primitive"
      pattern: "search\\("
    - from: "src/frontend/routes/fetch.ts"
      to: "src/sdk/fetch.ts"
      via: "validated route handler invoking SDK fetch primitive"
      pattern: "fetch\\("
    - from: "src/frontend/server.ts"
      to: "src/frontend/routes/search.ts"
      via: "Express route mounting under `/api/search`"
      pattern: "/api/search|router"
    - from: "src/frontend/server.ts"
      to: "src/frontend/routes/fetch.ts"
      via: "Express route mounting under `/api/fetch`"
      pattern: "/api/fetch|router"
---

<objective>
Create the backend half of the frontend validation surface so the browser can trigger both SDK primitives through a local API with explicit, inspectable results.

Purpose: Preserve SDK-first architecture and keep provider internals/secrets out of browser code while exposing clear operational feedback for debugging.
Output: Express server, validated API contracts/routes for `search` and `fetch`, and route tests that prove stable response envelopes.
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
@AGENTS.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Scaffold frontend server entrypoint and scripts</name>
  <files>package.json, src/frontend/server.ts</files>
  <action>Add a dedicated local frontend dev script (for example `dev:frontend`) and implement Express server bootstrap that enables JSON bodies, mounts API route modules under `/api/*`, serves static assets from `public`, and keeps all SDK invocation on the server side. Do not call SDK primitives directly from browser JavaScript.</action>
  <verify>`npm run typecheck` succeeds and running the frontend dev script starts a server exposing `/api/search` and `/api/fetch` endpoints.</verify>
  <done>Local frontend process exists and exposes stable API entrypoints for both operations.</done>
</task>

<task type="auto">
  <name>Task 2: Implement validated API contracts and route handlers</name>
  <files>src/frontend/contracts.ts, src/frontend/routes/search.ts, src/frontend/routes/fetch.ts</files>
  <action>Define zod schemas for request payloads and UI-safe response envelopes, then build route handlers that validate input, call SDK `search(...)`/`fetch(...)`, measure duration, and map failures into typed error envelopes with explicit `code`, `message`, and safe `details`. Keep return payloads normalized; do not leak provider-specific raw response shapes.</action>
  <verify>`npm run typecheck` passes and manual `curl` requests to both routes show structured success and validation error responses.</verify>
  <done>Both primitives are callable over local API with deterministic, inspectable envelopes.</done>
</task>

<task type="auto">
  <name>Task 3: Add route-level tests for contracts and error mapping</name>
  <files>src/tests/frontend-api/routes.contracts.test.ts</files>
  <action>Create Vitest coverage that mocks SDK success/failure paths and asserts route contract behavior: valid requests return `ok: true` with operation metadata, invalid payloads return `400` validation envelopes, and SDK failures return typed non-2xx envelopes with operation + duration. Include checks that errors from safety/compliance gates remain visible to the frontend caller.</action>
  <verify>`npm run test -- src/tests/frontend-api/routes.contracts.test.ts` passes.</verify>
  <done>API behavior for both operations is proven by executable tests, not manual inspection alone.</done>
</task>

</tasks>

<verification>
Run `npm run typecheck`, `npm run test -- src/tests/frontend-api/routes.contracts.test.ts`, and `npm run build`.
</verification>

<success_criteria>
- The frontend server exposes `/api/search` and `/api/fetch` with validated request contracts.
- Both routes call the SDK primitives and return normalized, inspectable envelopes with duration and operation metadata.
- Validation and operational failures are explicit and consistent for UI consumption.
</success_criteria>

<output>
After completion, create `.planning/phases/05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly/05-01-SUMMARY.md`
</output>
