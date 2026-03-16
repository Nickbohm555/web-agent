---
phase: 01-core-retrieval-engine
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - package.json
  - tsconfig.json
  - src/sdk/index.ts
  - src/sdk/contracts/search.ts
  - src/sdk/contracts/fetch.ts
  - src/tests/setup.test.ts
autonomous: true
must_haves:
  truths:
    - "A caller has one stable SDK entry module to import retrieval primitives and contract types from, rather than stitching multiple internal paths."
    - "At the SDK boundary, invalid search/fetch payloads are rejected and valid payloads parse into the documented normalized contract shapes."
    - "Equivalent search/fetch options normalize to the same parsed contract representation, so caller-visible behavior stays consistent regardless of input ordering/default omission."
  artifacts:
    - path: "package.json"
      provides: "Node/TypeScript scripts and dependencies for core retrieval execution"
    - path: "src/sdk/index.ts"
      provides: "Single public export surface for SDK methods and contracts"
    - path: "src/sdk/contracts/search.ts"
      provides: "Search request/result normalized zod contracts"
    - path: "src/sdk/contracts/fetch.ts"
      provides: "Fetch request/response normalized zod contracts"
  key_links:
    - from: "src/sdk/index.ts"
      to: "src/sdk/contracts/search.ts"
      via: "public contract export wiring"
      pattern: "export.*from.*contracts/search"
    - from: "src/sdk/index.ts"
      to: "src/sdk/contracts/fetch.ts"
      via: "public contract export wiring"
      pattern: "export.*from.*contracts/fetch"
    - from: "src/tests/setup.test.ts"
      to: "package.json"
      via: "baseline execution gates"
      pattern: "(vitest|npm run (typecheck|test|build))"
---

<objective>
Create a narrow, execution-ready foundation for Phase 01 so later plans can implement full search/fetch behavior without setup churn.

Purpose: Establish stable public boundaries and baseline project execution gates before provider/scraper implementation details are added.
Output: Scaffolded TypeScript project, SDK entry export surface, and strict search/fetch contract schemas.
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
@.planning/phases/01-core-retrieval-engine/01-RESEARCH.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Bootstrap TypeScript retrieval workspace</name>
  <files>package.json, tsconfig.json, src/sdk/index.ts, src/tests/setup.test.ts</files>
  <action>Initialize project files for Node 24 TypeScript execution. Add scripts `typecheck`, `test`, `test:watch`, `build`, `dev` and dependencies recommended by Phase 01 research (`undici`, `zod`, `p-retry`, `p-queue`, `pino`, `robots-parser`, `tldts`, `@mozilla/readability`, `turndown`, `cheerio`, plus test/build dev dependencies). Create `src/sdk/index.ts` as the public export surface for `search` and `fetch` entry points implemented by downstream plans. Add a minimal setup test that verifies test runner + TypeScript test scaffolding executes in CI.</action>
  <verify>`npm install && npm run typecheck && npm run test -- src/tests/setup.test.ts` completes successfully.</verify>
  <done>Repository can install, typecheck, and run baseline tests with a stable SDK export surface in place.</done>
</task>

<task type="auto">
  <name>Task 2: Define strict SDK boundary contracts</name>
  <files>src/sdk/contracts/search.ts, src/sdk/contracts/fetch.ts</files>
  <action>Create zod schemas and exported TypeScript types for search/fetch input and output shapes. Search result contract must include `title`, `url`, `snippet`, and rank metadata; fetch contract must expose consistent content structure (including text/markdown channel plus metadata and fallback reason fields). Include normalization helpers for canonical option defaults so equivalent inputs normalize to identical parsed representations. Keep provider payload structures out of these contracts and reserve adapter-specific typing for later plans.</action>
  <verify>`npm run test -- src/tests/setup.test.ts` passes with assertions that malformed inputs are rejected and valid normalized structures parse successfully.</verify>
  <done>Public contract source of truth exists for CORE-01 and CORE-02 and can be imported by both adapters and SDK methods.</done>
</task>

</tasks>

<verification>
Run `npm run typecheck`, `npm run test`, and `npm run build` after scaffold and contracts are in place.
</verification>

<success_criteria>
- Core foundation compiles, baseline tests run, and build gate is executable.
- Contract files enforce normalized public boundaries for both primitives.
- Downstream plans can implement provider/scraper logic without redefining SDK contract surfaces.
</success_criteria>

<output>
After completion, create `.planning/phases/01-core-retrieval-engine/01-01-SUMMARY.md`
</output>
