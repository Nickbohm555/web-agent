---
phase: 01-local-runtime-foundation
plan: 02
type: execute
wave: 2
depends_on: ["01-01"]
files_modified:
  - backend/app/config.py
  - backend/app/main.py
  - backend/requirements.txt
  - backend/tests/test_startup_settings.py
autonomous: true
user_setup:
  - service: openai
    why: "Backend requires model-provider credentials at runtime."
    env_vars:
      - name: OPENAI_API_KEY
        source: "OpenAI dashboard API keys page"
  - service: serper
    why: "Search tool integration requires provider credentials at runtime."
    env_vars:
      - name: SERPER_API_KEY
        source: "Serper dashboard API keys page"
must_haves:
  truths:
    - "Backend refuses to start when either required API key is missing."
    - "Backend starts cleanly when both keys are provided via environment variables."
    - "After startup, both backend and frontend are reachable locally."
  artifacts:
    - path: "backend/app/config.py"
      provides: "Typed settings model with required OPENAI_API_KEY and SERPER_API_KEY."
      exports: ["Settings", "get_settings"]
    - path: "backend/app/main.py"
      provides: "FastAPI lifespan startup validation and health endpoint."
      contains: ["lifespan", "/healthz"]
    - path: "backend/tests/test_startup_settings.py"
      provides: "Regression tests for missing-key failure and valid-key startup behavior."
  key_links:
    - from: "backend/app/main.py"
      to: "backend/app/config.py"
      via: "lifespan settings instantiation"
      pattern: "Settings\\(\\)"
    - from: "docker-compose.yml"
      to: "backend/app/main.py"
      via: "healthcheck endpoint probe"
      pattern: "/healthz"
    - from: "backend/tests/test_startup_settings.py"
      to: "backend/app/config.py"
      via: "startup validation assertions"
      pattern: "ValidationError|missing"
---

<objective>
Implement backend runtime settings loading and startup-time key validation so missing environment keys fail immediately and valid configuration boots cleanly.

Purpose: Completes `RUNTIME-04` and finalizes Phase 1 runtime acceptance behavior for clear failure/ready signals.
Output: Typed backend settings, startup validation wiring, startup tests, and reproducible reachability verification commands.
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
@.planning/phases/01-local-runtime-foundation/01-RESEARCH.md
@.planning/phases/01-local-runtime-foundation/01-01-define-docker-compose-services-and-shared-runtime-wiring-PLAN.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: Implement typed backend settings and startup validation</name>
  <files>backend/app/config.py, backend/app/main.py, backend/requirements.txt</files>
  <action>Add `pydantic-settings` dependency if missing, then implement `Settings` in `backend/app/config.py` with required `OPENAI_API_KEY` and `SERPER_API_KEY` fields and an accessor helper (`get_settings`) suitable for reuse. Wire FastAPI app startup in `backend/app/main.py` using lifespan so settings are instantiated before serving requests; missing required keys must raise a clear startup error and stop boot. Expose `/healthz` endpoint used by Compose healthcheck. Avoid lazy key reads inside tool functions for this phase; validation must happen at startup boundary.</action>
  <verify>Run backend tests for settings/startup plus `docker compose up --build --wait`; confirm startup fails fast when keys are missing and succeeds when keys are present.</verify>
  <done>Backend runtime has centralized typed settings and deterministic startup-time validation for both required keys.</done>
</task>

<task type="auto">
  <name>Task 2: Add startup configuration regression tests</name>
  <files>backend/tests/test_startup_settings.py</files>
  <action>Create tests covering: (a) missing `OPENAI_API_KEY` fails startup validation, (b) missing `SERPER_API_KEY` fails startup validation, (c) both keys present allows startup path and settings access. Use test patterns compatible with current backend test stack (pytest/FastAPI test client/lifespan helpers) and isolate environment mutations per test so cases are deterministic.</action>
  <verify>Run `pytest backend/tests/test_startup_settings.py` (or project-equivalent backend test command) and confirm all startup validation cases pass.</verify>
  <done>Automated tests protect required-key behavior and prevent silent regressions in runtime validation.</done>
</task>

<task type="auto">
  <name>Task 3: Validate local stack reachability and failure semantics</name>
  <files>docker-compose.yml</files>
  <action>Execute runtime acceptance checks using Compose contract from Plan 01-01: run with missing keys and verify clear interpolation/startup failure; run with both keys set and verify healthy startup with `docker compose up --build --wait`, then probe backend (`/healthz`) and frontend HTTP endpoint from host. If any probe path differs from implementation, update compose healthcheck and related docs/tests in the same change so probes reflect real runtime behavior.</action>
  <verify>Commands succeed in happy path: `docker compose up --build --wait`, `curl -f http://localhost:8000/healthz`, and frontend probe; failure path emits explicit missing-key error when key vars are absent.</verify>
  <done>Phase-1 runtime criteria are demonstrably met for both failure and success startup paths.</done>
</task>

</tasks>

<verification>
1. Unset one key and run `docker compose up --build` to verify clear failure message.
2. Export both keys and run `docker compose up --build --wait`.
3. Verify `docker compose ps` shows healthy/running services.
4. Probe backend and frontend local URLs and confirm 2xx responses.
</verification>

<success_criteria>
- Backend startup behavior clearly enforces `OPENAI_API_KEY` and `SERPER_API_KEY`.
- Runtime succeeds only when both keys are present in environment.
- Backend and frontend are both locally reachable after successful stack startup.
</success_criteria>

<output>
After completion, create `.planning/phases/01-local-runtime-foundation/01-02-SUMMARY.md`
</output>
