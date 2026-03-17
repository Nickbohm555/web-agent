---
phase: 01-local-runtime-foundation
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - docker-compose.yml
  - backend/Dockerfile
  - frontend/Dockerfile
autonomous: true
must_haves:
  truths:
    - "User can start backend and frontend together with one Docker Compose command."
    - "Compose startup enforces required API key variables before creating containers."
    - "Backend and frontend expose stable local ports for follow-up reachability checks."
  artifacts:
    - path: "docker-compose.yml"
      provides: "Two-service local stack contract with build, ports, env wiring, and healthcheck scaffolding."
      contains: ["services.backend", "services.frontend", "depends_on", "healthcheck"]
    - path: "backend/Dockerfile"
      provides: "Reproducible backend container image used by Compose."
    - path: "frontend/Dockerfile"
      provides: "Reproducible frontend container image used by Compose."
  key_links:
    - from: "docker-compose.yml"
      to: "backend"
      via: "environment interpolation"
      pattern: "OPENAI_API_KEY: \\$\\{OPENAI_API_KEY:\\?.+\\}"
    - from: "docker-compose.yml"
      to: "backend"
      via: "healthcheck probe"
      pattern: "curl -f http://localhost:8000/healthz"
    - from: "docker-compose.yml"
      to: "frontend"
      via: "depends_on condition"
      pattern: "condition: service_healthy"
---

<objective>
Define Docker Compose as the single local runtime entrypoint for backend and frontend, including required environment-variable wiring and startup dependency semantics.

Purpose: Satisfies `RUNTIME-01` foundation by removing manual multi-service bootstrapping and establishing deterministic startup order.
Output: A runnable `docker-compose.yml` plus Dockerfiles for both services, with health/dependency wiring ready for startup validation in the next plan.
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
</context>

<tasks>

<task type="auto">
  <name>Task 1: Create compose runtime contract for backend + frontend</name>
  <files>docker-compose.yml</files>
  <action>Create root `docker-compose.yml` with exactly two services (`backend`, `frontend`) on the same default network, explicit local port mappings, and long-form `depends_on` so `frontend` waits on `backend` health. In backend service `environment`, require both keys using `${OPENAI_API_KEY:?OPENAI_API_KEY is required}` and `${SERPER_API_KEY:?SERPER_API_KEY is required}` (no empty-string defaults, no optional fallback). Add backend healthcheck that probes `http://localhost:8000/healthz` and frontend healthcheck that probes its local HTTP endpoint. Keep compose file focused on local runtime only (no production-only config).</action>
  <verify>Run `docker compose config` and confirm interpolation errors are thrown when either required key is unset; then run `docker compose config` with both keys set and confirm both services resolve.</verify>
  <done>`docker-compose.yml` defines both services, required-key enforcement, and health-gated dependency order without manual bootstrap assumptions.</done>
</task>

<task type="auto">
  <name>Task 2: Add container build definitions used by Compose</name>
  <files>backend/Dockerfile, frontend/Dockerfile</files>
  <action>Create `backend/Dockerfile` and `frontend/Dockerfile` aligned with each service runtime so Compose can build both images from source. Backend image must run FastAPI process command and include tools needed by healthcheck probe. Frontend image must run the UI/server process used for local access. Keep Dockerfiles minimal and deterministic (set workdir, copy dependency manifests before source for cache efficiency, install deps, then run startup command).</action>
  <verify>Run `docker compose build backend frontend` and confirm both images build successfully with no missing file/path errors.</verify>
  <done>Compose can build both services from repository files without manual pre-built images.</done>
</task>

</tasks>

<verification>
Run `docker compose config`, `docker compose build`, and `docker compose up --wait` (after Plan 01-02) to confirm the runtime contract is structurally valid and ready for health-gated startup.
</verification>

<success_criteria>
- One command (`docker compose up --build --wait`) is the intended startup entrypoint for both services.
- Missing `OPENAI_API_KEY` or `SERPER_API_KEY` is surfaced as a clear Compose interpolation failure before container startup.
- Backend and frontend service definitions are wired for deterministic local startup order.
</success_criteria>

<output>
After completion, create `.planning/phases/01-local-runtime-foundation/01-01-SUMMARY.md`
</output>
