Tasks are in **required implementation order** (1...n). Each section = one context window. Complete one section at a time.
Current section to work on: section 32. (move +1 after each turn)

## Summary Creation Instructions

Use this guide any time a section references `SUMMARY.md` creation.

**Purpose**
- Execute a phase prompt (`PLAN.md`) and create the outcome summary (`SUMMARY.md`).

**Required reading before writing**
- Read `.planning/STATE.md` to load project context.
- Read `.planning/config.json` for planning behavior settings.

**How to create a good summary**
1. Identify the plan and summary file path: `.planning/phases/XX-name/{phase}-{plan}-SUMMARY.md`.
2. Read the executed `*-PLAN.md` and extract objective, tasks, verification requirements, success criteria, and output intent.
3. Gather execution evidence from git history (not memory):
   - `git log --oneline --grep="^<plan-id>-task[0-9]+$"`
   - `git show --stat --name-status <commit>` for each matching task commit.
4. Write the summary title as `# Phase [X] Plan [Y]: [Name] Summary`.
5. Add a substantive one-line outcome under the title.
   - Good: `JWT auth with refresh rotation using jose library`
   - Bad: `Authentication implemented`
6. Populate frontmatter from execution context:
   - `phase`, `plan`, `subsystem`, `tags`
   - `requires`, `provides`, `affects`
   - `tech-stack.added`, `tech-stack.patterns`
   - `key-files.created`, `key-files.modified`
   - `key-decisions`
   - `duration` (from `$DURATION`), `completed` (from `$PLAN_END_TIME`, `YYYY-MM-DD`)
7. Ensure claims map to evidence from task commits, and preserve task-to-commit traceability.
8. Include a deviations section:
   - If none: state the plan executed as written.
   - If present: list rule triggered, change made, verification performed, and commit hash.
9. Keep the summary focused on what was actually delivered, verified, and learned.

## Loop Commit Contract

- Do **not** run `git commit` or `git push` directly in execution steps.
- `.loop-commit-msg` must contain exactly one non-empty line.
- Use exactly one commit subject format from this list:
  - Task sections: `{phase-number}-{plan-number}-task{task-number}` (example: `01-01-task1`)
  - Test sections: `{phase-number}-{plan-number}-test{test-number}` (example: `01-01-test1`)
  - Summary sections: `{phase-number}-{plan-number}-summary` (example: `01-01-summary`)

## Section 1 — 01-local-runtime-foundation — 01-01-define-docker-compose-services-and-shared-runtime-wiring — Task 1 (Execution)

**Required Inputs**
- Plan: `.planning/phases/01-local-runtime-foundation/01-01-define-docker-compose-services-and-shared-runtime-wiring-PLAN.md`
- Phase research: `.planning/phases/01-local-runtime-foundation/01-RESEARCH.md`

**Steps**
1. Load `.planning/phases/01-local-runtime-foundation/01-RESEARCH.md` and use it as a reference while executing this task.
2. If a phase context file is added later, load it and treat it as the phase vision before implementation.
3. Execute Task 1 action: create `docker-compose.yml` with exactly `backend` and `frontend`, required env var interpolation for `OPENAI_API_KEY` and `SERPER_API_KEY`, explicit port mappings, healthchecks, and long-form `depends_on` so frontend waits for backend health.
4. Run task verification checks one-by-one: run `docker compose config` with missing keys to confirm interpolation errors, then with both keys set to confirm both services resolve.
5. Do not mark this task complete until done condition is satisfied: compose defines both services, required-key enforcement, and health-gated startup assumptions.
6. Write `.loop-commit-msg` with exactly one non-empty line: `01-01-task1`.
7. Update `.planning/STATE.md` with `phase=01-local-runtime-foundation` / `plan=01-01-define-docker-compose-services-and-shared-runtime-wiring` / `task=1` / `status=implemented`.

## Section 2 — 01-local-runtime-foundation — 01-01-define-docker-compose-services-and-shared-runtime-wiring — Task 2 (Execution)

**Required Inputs**
- Plan: `.planning/phases/01-local-runtime-foundation/01-01-define-docker-compose-services-and-shared-runtime-wiring-PLAN.md`
- Phase research: `.planning/phases/01-local-runtime-foundation/01-RESEARCH.md`

**Steps**
1. Load `.planning/phases/01-local-runtime-foundation/01-RESEARCH.md` and use it as a reference while executing this task.
2. If a phase context file is added later, load it and treat it as the phase vision before implementation.
3. Execute Task 2 action: add `backend/Dockerfile` and `frontend/Dockerfile` with deterministic build steps, runtime commands, and backend healthcheck dependencies available in-image.
4. Run task verification checks one-by-one: run `docker compose build backend frontend` and confirm both images build successfully.
5. Do not mark this task complete until done condition is satisfied: compose can build both services directly from repository files.
6. Write `.loop-commit-msg` with exactly one non-empty line: `01-01-task2`.
7. Update `.planning/STATE.md` with `phase=01-local-runtime-foundation` / `plan=01-01-define-docker-compose-services-and-shared-runtime-wiring` / `task=2` / `status=implemented`.

## Section 3 — 01-local-runtime-foundation — 01-01-define-docker-compose-services-and-shared-runtime-wiring (Summary)

**Required Inputs**
- Plan: `.planning/phases/01-local-runtime-foundation/01-01-define-docker-compose-services-and-shared-runtime-wiring-PLAN.md`
- Phase research: `.planning/phases/01-local-runtime-foundation/01-RESEARCH.md`

**Steps**
1. Create `.planning/phases/01-local-runtime-foundation/01-01-SUMMARY.md` by following `## Summary Creation Instructions` in this file.
2. Write `.loop-commit-msg` with exactly one non-empty line: `01-01-summary`.

## Section 4 — 01-local-runtime-foundation — 01-02-implement-environment-configuration-loading-and-startup-validation — Task 1 (Execution)

**Required Inputs**
- Plan: `.planning/phases/01-local-runtime-foundation/01-02-implement-environment-configuration-loading-and-startup-validation-PLAN.md`
- Phase research: `.planning/phases/01-local-runtime-foundation/01-RESEARCH.md`

**Steps**
1. Load `.planning/phases/01-local-runtime-foundation/01-RESEARCH.md` and use it as a reference while executing this task.
2. If a phase context file is added later, load it and treat it as the phase vision before implementation.
3. Execute Task 1 action: add `pydantic-settings` if missing, implement typed `Settings` and `get_settings` in `backend/app/config.py`, wire startup validation in `backend/app/main.py` lifespan, and expose `/healthz`.
4. Run task verification checks one-by-one: run startup/settings backend tests and `docker compose up --build --wait` for missing-key and present-key behavior.
5. Do not mark this task complete until done condition is satisfied: centralized typed settings and deterministic startup validation for both required keys.
6. Write `.loop-commit-msg` with exactly one non-empty line: `01-02-task1`.
7. Update `.planning/STATE.md` with `phase=01-local-runtime-foundation` / `plan=01-02-implement-environment-configuration-loading-and-startup-validation` / `task=1` / `status=implemented`.

## Section 5 — 01-local-runtime-foundation — 01-02-implement-environment-configuration-loading-and-startup-validation — Task 2 (Execution)

**Required Inputs**
- Plan: `.planning/phases/01-local-runtime-foundation/01-02-implement-environment-configuration-loading-and-startup-validation-PLAN.md`
- Phase research: `.planning/phases/01-local-runtime-foundation/01-RESEARCH.md`

**Steps**
1. Load `.planning/phases/01-local-runtime-foundation/01-RESEARCH.md` and use it as a reference while executing this task.
2. If a phase context file is added later, load it and treat it as the phase vision before implementation.
3. Execute Task 2 action: add `backend/tests/test_startup_settings.py` coverage for missing `OPENAI_API_KEY`, missing `SERPER_API_KEY`, and successful startup when both are present.
4. Run task verification checks one-by-one: run `pytest backend/tests/test_startup_settings.py` (or project-equivalent command) and confirm all cases pass.
5. Do not mark this task complete until done condition is satisfied: automated tests protect required-key runtime behavior.
6. Write `.loop-commit-msg` with exactly one non-empty line: `01-02-task2`.
7. Update `.planning/STATE.md` with `phase=01-local-runtime-foundation` / `plan=01-02-implement-environment-configuration-loading-and-startup-validation` / `task=2` / `status=implemented`.

## Section 6 — 01-local-runtime-foundation — 01-02-implement-environment-configuration-loading-and-startup-validation — Task 3 (Execution)

**Required Inputs**
- Plan: `.planning/phases/01-local-runtime-foundation/01-02-implement-environment-configuration-loading-and-startup-validation-PLAN.md`
- Phase research: `.planning/phases/01-local-runtime-foundation/01-RESEARCH.md`

**Steps**
1. Load `.planning/phases/01-local-runtime-foundation/01-RESEARCH.md` and use it as a reference while executing this task.
2. If a phase context file is added later, load it and treat it as the phase vision before implementation.
3. Execute Task 3 action: validate compose failure semantics with missing keys and successful startup/reachability for backend and frontend with keys present; align probes if needed.
4. Run task verification checks one-by-one: `docker compose up --build --wait`, `curl -f http://localhost:8000/healthz`, and frontend HTTP probe; verify explicit missing-key failures when env vars are absent.
5. Do not mark this task complete until done condition is satisfied: Phase 1 runtime success/failure criteria are demonstrably met.
6. Write `.loop-commit-msg` with exactly one non-empty line: `01-02-task3`.
7. Update `.planning/STATE.md` with `phase=01-local-runtime-foundation` / `plan=01-02-implement-environment-configuration-loading-and-startup-validation` / `task=3` / `status=implemented`.

## Section 7 — 01-local-runtime-foundation — 01-02-implement-environment-configuration-loading-and-startup-validation (Summary)

**Required Inputs**
- Plan: `.planning/phases/01-local-runtime-foundation/01-02-implement-environment-configuration-loading-and-startup-validation-PLAN.md`
- Phase research: `.planning/phases/01-local-runtime-foundation/01-RESEARCH.md`

**Steps**
1. Create `.planning/phases/01-local-runtime-foundation/01-02-SUMMARY.md` by following `## Summary Creation Instructions` in this file.
2. Because this summary completes Phase 01, include the roadmap/state completion update in this summary section while still using a summary commit subject.
3. Write `.loop-commit-msg` with exactly one non-empty line: `01-02-summary`.

## Section 8 — 02-search-and-crawl-tool-capability — 02-01-implement-serper-backed-web-search-tool-in-python — Task 1 (Execution)

**Required Inputs**
- Plan: `.planning/phases/02-search-and-crawl-tool-capability/02-01-implement-serper-backed-web-search-tool-in-python-PLAN.md`
- Phase research: `.planning/phases/02-search-and-crawl-tool-capability/02-RESEARCH.md`

**Steps**
1. Load `.planning/phases/02-search-and-crawl-tool-capability/02-RESEARCH.md` and use it as a reference while executing this task.
2. If a phase context file is added later, load it and treat it as the phase vision before implementation.
3. Execute Task 1 action: create strict Pydantic contracts for tool errors and normalized web search input/result/success envelopes without exposing raw Serper field names.
4. Run task verification checks one-by-one: run backend tests that instantiate valid/invalid contract payloads and verify deterministic validation behavior.
5. Do not mark this task complete until done condition is satisfied: search and error contracts are importable typed models with explicit validation guarantees.
6. Write `.loop-commit-msg` with exactly one non-empty line: `02-01-task1`.
7. Update `.planning/STATE.md` with `phase=02-search-and-crawl-tool-capability` / `plan=02-01-implement-serper-backed-web-search-tool-in-python` / `task=1` / `status=implemented`.

## Section 9 — 02-search-and-crawl-tool-capability — 02-01-implement-serper-backed-web-search-tool-in-python — Task 2 (Execution)

**Required Inputs**
- Plan: `.planning/phases/02-search-and-crawl-tool-capability/02-01-implement-serper-backed-web-search-tool-in-python-PLAN.md`
- Phase research: `.planning/phases/02-search-and-crawl-tool-capability/02-RESEARCH.md`

**Steps**
1. Load `.planning/phases/02-search-and-crawl-tool-capability/02-RESEARCH.md` and use it as a reference while executing this task.
2. If a phase context file is added later, load it and treat it as the phase vision before implementation.
3. Execute Task 2 action: implement Serper client with bounded tenacity retries (max 3, exponential backoff) for retryable classes, strict timeout, deterministic normalization, and fail-fast non-retryable 4xx behavior.
4. Run task verification checks one-by-one: run mocked HTTP tests for 200, 429->200 recovery, terminal 500 failure, and 400 fail-fast.
5. Do not mark this task complete until done condition is satisfied: Serper transport produces normalized contract-valid results and typed retry outcomes.
6. Write `.loop-commit-msg` with exactly one non-empty line: `02-01-task2`.
7. Update `.planning/STATE.md` with `phase=02-search-and-crawl-tool-capability` / `plan=02-01-implement-serper-backed-web-search-tool-in-python` / `task=2` / `status=implemented`.

## Section 10 — 02-search-and-crawl-tool-capability — 02-01-implement-serper-backed-web-search-tool-in-python — Task 3 (Execution)

**Required Inputs**
- Plan: `.planning/phases/02-search-and-crawl-tool-capability/02-01-implement-serper-backed-web-search-tool-in-python-PLAN.md`
- Phase research: `.planning/phases/02-search-and-crawl-tool-capability/02-RESEARCH.md`

**Steps**
1. Load `.planning/phases/02-search-and-crawl-tool-capability/02-RESEARCH.md` and use it as a reference while executing this task.
2. If a phase context file is added later, load it and treat it as the phase vision before implementation.
3. Execute Task 3 action: expose `@tool("web_search")` adapter with strict args schema that always returns contract-valid success or explicit error envelopes.
4. Run task verification checks one-by-one: run `pytest backend/tests/tools/test_web_search_tool.py`.
5. Do not mark this task complete until done condition is satisfied: `web_search` is callable and returns stable normalized outputs with debuggable failure semantics.
6. Write `.loop-commit-msg` with exactly one non-empty line: `02-01-task3`.
7. Update `.planning/STATE.md` with `phase=02-search-and-crawl-tool-capability` / `plan=02-01-implement-serper-backed-web-search-tool-in-python` / `task=3` / `status=implemented`.

## Section 11 — 02-search-and-crawl-tool-capability — 02-01-implement-serper-backed-web-search-tool-in-python (Summary)

**Required Inputs**
- Plan: `.planning/phases/02-search-and-crawl-tool-capability/02-01-implement-serper-backed-web-search-tool-in-python-PLAN.md`
- Phase research: `.planning/phases/02-search-and-crawl-tool-capability/02-RESEARCH.md`

**Steps**
1. Create `.planning/phases/02-search-and-crawl-tool-capability/02-01-SUMMARY.md` by following `## Summary Creation Instructions` in this file.
2. Write `.loop-commit-msg` with exactly one non-empty line: `02-01-summary`.

## Section 12 — 02-search-and-crawl-tool-capability — 02-02-implement-in-house-python-web-crawl-extraction-flow — Task 1 (Execution)

**Required Inputs**
- Plan: `.planning/phases/02-search-and-crawl-tool-capability/02-02-implement-in-house-python-web-crawl-extraction-flow-PLAN.md`
- Phase research: `.planning/phases/02-search-and-crawl-tool-capability/02-RESEARCH.md`

**Steps**
1. Load `.planning/phases/02-search-and-crawl-tool-capability/02-RESEARCH.md` and use it as a reference while executing this task.
2. If a phase context file is added later, load it and treat it as the phase vision before implementation.
3. Execute Task 1 action: define crawl contracts and implement HTTP-first worker with bounded retry, redirects, content-type inspection, response-size guardrails, and typed terminal/retry failure mapping.
4. Run task verification checks one-by-one: run mocked tests for html 200, redirect final URL capture, unsupported content type, timeout/retry behavior, and terminal 4xx classification.
5. Do not mark this task complete until done condition is satisfied: crawl fetch path provides deterministic typed outcomes and correct retry/terminal classification.
6. Write `.loop-commit-msg` with exactly one non-empty line: `02-02-task1`.
7. Update `.planning/STATE.md` with `phase=02-search-and-crawl-tool-capability` / `plan=02-02-implement-in-house-python-web-crawl-extraction-flow` / `task=1` / `status=implemented`.

## Section 13 — 02-search-and-crawl-tool-capability — 02-02-implement-in-house-python-web-crawl-extraction-flow — Task 2 (Execution)

**Required Inputs**
- Plan: `.planning/phases/02-search-and-crawl-tool-capability/02-02-implement-in-house-python-web-crawl-extraction-flow-PLAN.md`
- Phase research: `.planning/phases/02-search-and-crawl-tool-capability/02-RESEARCH.md`

**Steps**
1. Load `.planning/phases/02-search-and-crawl-tool-capability/02-RESEARCH.md` and use it as a reference while executing this task.
2. If a phase context file is added later, load it and treat it as the phase vision before implementation.
3. Execute Task 2 action: implement Trafilatura extraction state machine returning markdown/text and explicit states (`ok`, `low-content-quality`, `unsupported-content-type`, `network-error`) with deterministic quality threshold and fallback reason mapping.
4. Run task verification checks one-by-one: run extraction tests with rich-content, boilerplate-only, and non-HTML fixtures.
5. Do not mark this task complete until done condition is satisfied: extraction is never silently empty and all non-success outcomes are explicit.
6. Write `.loop-commit-msg` with exactly one non-empty line: `02-02-task2`.
7. Update `.planning/STATE.md` with `phase=02-search-and-crawl-tool-capability` / `plan=02-02-implement-in-house-python-web-crawl-extraction-flow` / `task=2` / `status=implemented`.

## Section 14 — 02-search-and-crawl-tool-capability — 02-02-implement-in-house-python-web-crawl-extraction-flow — Task 3 (Execution)

**Required Inputs**
- Plan: `.planning/phases/02-search-and-crawl-tool-capability/02-02-implement-in-house-python-web-crawl-extraction-flow-PLAN.md`
- Phase research: `.planning/phases/02-search-and-crawl-tool-capability/02-RESEARCH.md`

**Steps**
1. Load `.planning/phases/02-search-and-crawl-tool-capability/02-RESEARCH.md` and use it as a reference while executing this task.
2. If a phase context file is added later, load it and treat it as the phase vision before implementation.
3. Execute Task 3 action: expose `@tool("web_crawl")` with strict schema and flow `validate -> http worker -> extractor -> contract response`, preserving shared error envelope semantics.
4. Run task verification checks one-by-one: run `pytest backend/tests/tools/test_web_crawl_tool.py`.
5. Do not mark this task complete until done condition is satisfied: `web_crawl` is callable with stable output schema and explicit failure semantics.
6. Write `.loop-commit-msg` with exactly one non-empty line: `02-02-task3`.
7. Update `.planning/STATE.md` with `phase=02-search-and-crawl-tool-capability` / `plan=02-02-implement-in-house-python-web-crawl-extraction-flow` / `task=3` / `status=implemented`.

## Section 15 — 02-search-and-crawl-tool-capability — 02-02-implement-in-house-python-web-crawl-extraction-flow (Summary)

**Required Inputs**
- Plan: `.planning/phases/02-search-and-crawl-tool-capability/02-02-implement-in-house-python-web-crawl-extraction-flow-PLAN.md`
- Phase research: `.planning/phases/02-search-and-crawl-tool-capability/02-RESEARCH.md`

**Steps**
1. Create `.planning/phases/02-search-and-crawl-tool-capability/02-02-SUMMARY.md` by following `## Summary Creation Instructions` in this file.
2. Because this summary completes Phase 02, include the roadmap/state completion update in this summary section while still using a summary commit subject.
3. Write `.loop-commit-msg` with exactly one non-empty line: `02-02-summary`.

## Section 16 — 03-agent-execution-loop-and-api — 03-01 — Task 1 (Execution)

**Required Inputs**
- Plan: `.planning/phases/03-agent-execution-loop-and-api/03-01-PLAN.md`
- Phase research: `.planning/phases/03-agent-execution-loop-and-api/03-RESEARCH.md`

**Steps**
1. Load `.planning/phases/03-agent-execution-loop-and-api/03-RESEARCH.md` and use it as a reference while executing this task.
2. If a phase context file is added later, load it and treat it as the phase vision before implementation.
3. Execute Task 1 action: implement runtime facade (`run_agent_once`) that binds exactly `web_search` and `web_crawl`, asserts canonical names, and maps raw runtime output to normalized internal `AgentRunResult`.
4. Run task verification checks one-by-one: run `pytest backend/tests/agent/test_runtime.py -q`.
5. Do not mark this task complete until done condition is satisfied: one prompt run executes end-to-end with normalized output and no provider payload leakage.
6. Write `.loop-commit-msg` with exactly one non-empty line: `03-01-task1`.
7. Update `.planning/STATE.md` with `phase=03-agent-execution-loop-and-api` / `plan=03-01` / `task=1` / `status=implemented`.

## Section 17 — 03-agent-execution-loop-and-api — 03-01 — Task 2 (Execution)

**Required Inputs**
- Plan: `.planning/phases/03-agent-execution-loop-and-api/03-01-PLAN.md`
- Phase research: `.planning/phases/03-agent-execution-loop-and-api/03-RESEARCH.md`

**Steps**
1. Load `.planning/phases/03-agent-execution-loop-and-api/03-RESEARCH.md` and use it as a reference while executing this task.
2. If a phase context file is added later, load it and treat it as the phase vision before implementation.
3. Execute Task 2 action: enforce bounded execution (`recursion_limit` or equivalent), preserve stop strategy in system instructions, and map known runtime failures into explicit internal error categories.
4. Run task verification checks one-by-one: run `pytest backend/tests/agent/test_runtime.py -q -k "recursion or failure or timeout"`.
5. Do not mark this task complete until done condition is satisfied: normal runs terminate, forced-loop/failure paths return deterministic typed errors, and no unbounded path remains.
6. Write `.loop-commit-msg` with exactly one non-empty line: `03-01-task2`.
7. Update `.planning/STATE.md` with `phase=03-agent-execution-loop-and-api` / `plan=03-01` / `task=2` / `status=implemented`.

## Section 18 — 03-agent-execution-loop-and-api — 03-01 (Summary)

**Required Inputs**
- Plan: `.planning/phases/03-agent-execution-loop-and-api/03-01-PLAN.md`
- Phase research: `.planning/phases/03-agent-execution-loop-and-api/03-RESEARCH.md`

**Steps**
1. Create `.planning/phases/03-agent-execution-loop-and-api/03-01-SUMMARY.md` by following `## Summary Creation Instructions` in this file.
2. Write `.loop-commit-msg` with exactly one non-empty line: `03-01-summary`.

## Section 19 — 03-agent-execution-loop-and-api — 03-02 — Task 1 (Execution)

**Required Inputs**
- Plan: `.planning/phases/03-agent-execution-loop-and-api/03-02-PLAN.md`
- Phase research: `.planning/phases/03-agent-execution-loop-and-api/03-RESEARCH.md`

**Steps**
1. Load `.planning/phases/03-agent-execution-loop-and-api/03-RESEARCH.md` and use it as a reference while executing this task.
2. If a phase context file is added later, load it and treat it as the phase vision before implementation.
3. Execute Task 1 action: define stable API request/response contracts and structured error envelope with deterministic runtime-error-to-HTTP mapping.
4. Run task verification checks one-by-one: run `pytest backend/tests/api/test_agent_run_route.py -q -k "contract or validation or error"`.
5. Do not mark this task complete until done condition is satisfied: invalid payloads fail cleanly, success envelope fields remain stable, and known runtime failures map to explicit API errors.
6. Write `.loop-commit-msg` with exactly one non-empty line: `03-02-task1`.
7. Update `.planning/STATE.md` with `phase=03-agent-execution-loop-and-api` / `plan=03-02` / `task=1` / `status=implemented`.

## Section 20 — 03-agent-execution-loop-and-api — 03-02 — Task 2 (Execution)

**Required Inputs**
- Plan: `.planning/phases/03-agent-execution-loop-and-api/03-02-PLAN.md`
- Phase research: `.planning/phases/03-agent-execution-loop-and-api/03-RESEARCH.md`

**Steps**
1. Load `.planning/phases/03-agent-execution-loop-and-api/03-RESEARCH.md` and use it as a reference while executing this task.
2. If a phase context file is added later, load it and treat it as the phase vision before implementation.
3. Execute Task 2 action: implement `POST /api/agent/run` route, validate request, call runtime exactly once, return contract-approved fields, and wire route in app startup.
4. Run task verification checks one-by-one: run backend and smoke test with `uvicorn backend.main:app --reload` and `curl -s -X POST http://localhost:8000/api/agent/run -H 'content-type: application/json' -d '{"prompt":"find one source and summarize"}'`.
5. Do not mark this task complete until done condition is satisfied: endpoint is reachable, executes one bounded run, and returns stable answer + metadata.
6. Write `.loop-commit-msg` with exactly one non-empty line: `03-02-task2`.
7. Update `.planning/STATE.md` with `phase=03-agent-execution-loop-and-api` / `plan=03-02` / `task=2` / `status=implemented`.

## Section 21 — 03-agent-execution-loop-and-api — 03-02 — Task 3 (Execution)

**Required Inputs**
- Plan: `.planning/phases/03-agent-execution-loop-and-api/03-02-PLAN.md`
- Phase research: `.planning/phases/03-agent-execution-loop-and-api/03-RESEARCH.md`

**Steps**
1. Load `.planning/phases/03-agent-execution-loop-and-api/03-RESEARCH.md` and use it as a reference while executing this task.
2. If a phase context file is added later, load it and treat it as the phase vision before implementation.
3. Execute Task 3 action: add route integration tests for request validation, stable success envelope, and recursion/failure mapping into explicit API errors using deterministic runtime stubs/fixtures.
4. Run task verification checks one-by-one: run `pytest backend/tests/api/test_agent_run_route.py -q`.
5. Do not mark this task complete until done condition is satisfied: route behavior is deterministic in both success and failure paths and contract regressions fail tests.
6. Write `.loop-commit-msg` with exactly one non-empty line: `03-02-task3`.
7. Update `.planning/STATE.md` with `phase=03-agent-execution-loop-and-api` / `plan=03-02` / `task=3` / `status=implemented`.

## Section 22 — 03-agent-execution-loop-and-api — 03-02 (Summary)

**Required Inputs**
- Plan: `.planning/phases/03-agent-execution-loop-and-api/03-02-PLAN.md`
- Phase research: `.planning/phases/03-agent-execution-loop-and-api/03-RESEARCH.md`

**Steps**
1. Create `.planning/phases/03-agent-execution-loop-and-api/03-02-SUMMARY.md` by following `## Summary Creation Instructions` in this file.
2. Because this summary completes Phase 03, include the roadmap/state completion update in this summary section while still using a summary commit subject.
3. Write `.loop-commit-msg` with exactly one non-empty line: `03-02-summary`.

## Section 23 — 04-frontend-prompt-execution-surface — 04-01 — Task 1 (Execution)

**Required Inputs**
- Plan: `.planning/phases/04-frontend-prompt-execution-surface/04-01-PLAN.md`
- Phase research: `.planning/phases/04-frontend-prompt-execution-surface/04-RESEARCH.md`

**Steps**
1. Load `.planning/phases/04-frontend-prompt-execution-surface/04-RESEARCH.md` and use it as a reference while executing this task.
2. If a phase context file is added later, load it and treat it as the phase vision before implementation.
3. Execute Task 1 action: add typed run-start contracts (`{ prompt }` -> `{ runId, status }`), implement `createRunsRouter()`, wire `/api/runs` in server, and add contract tests for success + malformed payload rejection.
4. Run task verification checks one-by-one: run `npm run test -- src/tests/frontend-api/runs.contracts.test.ts`.
5. Do not mark this task complete until done condition is satisfied: `POST /api/runs` validates payloads, returns typed response, and tests pass.
6. Write `.loop-commit-msg` with exactly one non-empty line: `04-01-task1`.
7. Update `.planning/STATE.md` with `phase=04-frontend-prompt-execution-surface` / `plan=04-01` / `task=1` / `status=implemented`.

## Section 24 — 04-frontend-prompt-execution-surface — 04-01 — Task 2 (Execution)

**Required Inputs**
- Plan: `.planning/phases/04-frontend-prompt-execution-surface/04-01-PLAN.md`
- Phase research: `.planning/phases/04-frontend-prompt-execution-surface/04-RESEARCH.md`

**Steps**
1. Load `.planning/phases/04-frontend-prompt-execution-surface/04-RESEARCH.md` and use it as a reference while executing this task.
2. If a phase context file is added later, load it and treat it as the phase vision before implementation.
3. Execute Task 2 action: build one-screen prompt UI + typed API client + reducer for `idle -> starting -> running|failed` and wire submit flow to transitions.
4. Run task verification checks one-by-one: run `npm run typecheck && npm run test -- src/tests/frontend-api/runs.contracts.test.ts`.
5. Do not mark this task complete until done condition is satisfied: user can submit prompt and observe deterministic run-start state transitions.
6. Write `.loop-commit-msg` with exactly one non-empty line: `04-01-task2`.
7. Update `.planning/STATE.md` with `phase=04-frontend-prompt-execution-surface` / `plan=04-01` / `task=2` / `status=implemented`.

## Section 25 — 04-frontend-prompt-execution-surface — 04-01 (Summary)

**Required Inputs**
- Plan: `.planning/phases/04-frontend-prompt-execution-surface/04-01-PLAN.md`
- Phase research: `.planning/phases/04-frontend-prompt-execution-surface/04-RESEARCH.md`

**Steps**
1. Create `.planning/phases/04-frontend-prompt-execution-surface/04-01-SUMMARY.md` by following `## Summary Creation Instructions` in this file.
2. Write `.loop-commit-msg` with exactly one non-empty line: `04-01-summary`.

## Section 26 — 04-frontend-prompt-execution-surface — 04-02 — Task 1 (Execution)

**Required Inputs**
- Plan: `.planning/phases/04-frontend-prompt-execution-surface/04-02-PLAN.md`
- Phase research: `.planning/phases/04-frontend-prompt-execution-surface/04-RESEARCH.md`

**Steps**
1. Load `.planning/phases/04-frontend-prompt-execution-surface/04-RESEARCH.md` and use it as a reference while executing this task.
2. If a phase context file is added later, load it and treat it as the phase vision before implementation.
3. Execute Task 1 action: add strict run-event SSE contracts (`run_state`, `tool_call`, `run_complete`, `run_error`), EventSource stream plumbing, parse guards, and close behavior on terminal/new-run boundaries.
4. Run task verification checks one-by-one: run `npm run test -- src/tests/frontend-api/runs.stream.test.ts`.
5. Do not mark this task complete until done condition is satisfied: frontend can consume typed SSE stream safely and close stream resources correctly.
6. Write `.loop-commit-msg` with exactly one non-empty line: `04-02-task1`.
7. Update `.planning/STATE.md` with `phase=04-frontend-prompt-execution-surface` / `plan=04-02` / `task=1` / `status=implemented`.

## Section 27 — 04-frontend-prompt-execution-surface — 04-02 — Task 2 (Execution)

**Required Inputs**
- Plan: `.planning/phases/04-frontend-prompt-execution-surface/04-02-PLAN.md`
- Phase research: `.planning/phases/04-frontend-prompt-execution-surface/04-RESEARCH.md`

**Steps**
1. Load `.planning/phases/04-frontend-prompt-execution-surface/04-RESEARCH.md` and use it as a reference while executing this task.
2. If a phase context file is added later, load it and treat it as the phase vision before implementation.
3. Execute Task 2 action: enforce idempotent reducer updates keyed by `toolCallId`, monotonic run-phase rules, duplicate/out-of-order merge behavior, and terminal regression guards.
4. Run task verification checks one-by-one: run `npm run test -- src/tests/frontend/state.test.ts`.
5. Do not mark this task complete until done condition is satisfied: reducer is deterministic under duplication and reordering and exposes data ready for timeline rendering.
6. Write `.loop-commit-msg` with exactly one non-empty line: `04-02-task2`.
7. Update `.planning/STATE.md` with `phase=04-frontend-prompt-execution-surface` / `plan=04-02` / `task=2` / `status=implemented`.

## Section 28 — 04-frontend-prompt-execution-surface — 04-02 (Summary)

**Required Inputs**
- Plan: `.planning/phases/04-frontend-prompt-execution-surface/04-02-PLAN.md`
- Phase research: `.planning/phases/04-frontend-prompt-execution-surface/04-RESEARCH.md`

**Steps**
1. Create `.planning/phases/04-frontend-prompt-execution-surface/04-02-SUMMARY.md` by following `## Summary Creation Instructions` in this file.
2. Write `.loop-commit-msg` with exactly one non-empty line: `04-02-summary`.

## Section 29 — 04-frontend-prompt-execution-surface — 04-03 — Task 1 (Execution)

**Required Inputs**
- Plan: `.planning/phases/04-frontend-prompt-execution-surface/04-03-PLAN.md`
- Phase research: `.planning/phases/04-frontend-prompt-execution-surface/04-RESEARCH.md`

**Steps**
1. Load `.planning/phases/04-frontend-prompt-execution-surface/04-RESEARCH.md` and use it as a reference while executing this task.
2. If a phase context file is added later, load it and treat it as the phase vision before implementation.
3. Execute Task 1 action: add timeline projection helpers with deterministic ordering and duration precedence (provisional elapsed while running, backend `durationMs` once complete).
4. Run task verification checks one-by-one: run `npm run test -- src/tests/frontend/timeline.test.ts`.
5. Do not mark this task complete until done condition is satisfied: timeline helpers produce deterministic rows and correct duration behavior across states.
6. Write `.loop-commit-msg` with exactly one non-empty line: `04-03-task1`.
7. Update `.planning/STATE.md` with `phase=04-frontend-prompt-execution-surface` / `plan=04-03` / `task=1` / `status=implemented`.

## Section 30 — 04-frontend-prompt-execution-surface — 04-03 — Task 2 (Execution)

**Required Inputs**
- Plan: `.planning/phases/04-frontend-prompt-execution-surface/04-03-PLAN.md`
- Phase research: `.planning/phases/04-frontend-prompt-execution-surface/04-RESEARCH.md`

**Steps**
1. Load `.planning/phases/04-frontend-prompt-execution-surface/04-RESEARCH.md` and use it as a reference while executing this task.
2. If a phase context file is added later, load it and treat it as the phase vision before implementation.
3. Execute Task 2 action: render timeline rows with tool name/status/duration, sync terminal run outcomes, and preserve one-active-run semantics without adding Phase 5 payload/history panels.
4. Run task verification checks one-by-one: run `npm run typecheck && npm run test`.
5. Do not mark this task complete until done condition is satisfied: user sees live per-tool timeline and stable final state without duplicate rows across reruns.
6. Write `.loop-commit-msg` with exactly one non-empty line: `04-03-task2`.
7. Update `.planning/STATE.md` with `phase=04-frontend-prompt-execution-surface` / `plan=04-03` / `task=2` / `status=implemented`.

## Section 31 — 04-frontend-prompt-execution-surface — 04-03 (Summary)

**Required Inputs**
- Plan: `.planning/phases/04-frontend-prompt-execution-surface/04-03-PLAN.md`
- Phase research: `.planning/phases/04-frontend-prompt-execution-surface/04-RESEARCH.md`

**Steps**
1. Create `.planning/phases/04-frontend-prompt-execution-surface/04-03-SUMMARY.md` by following `## Summary Creation Instructions` in this file.
2. Because this summary completes Phase 04, include the roadmap/state completion update in this summary section while still using a summary commit subject.
3. Write `.loop-commit-msg` with exactly one non-empty line: `04-03-summary`.

## Section 32 — 05-end-to-end-observability-and-run-history — 05-01-add-full-tool-payload-rendering-in-ui — Task 1 (Execution)

**Required Inputs**
- Plan: `.planning/phases/05-end-to-end-observability-and-run-history/05-01-add-full-tool-payload-rendering-in-ui-PLAN.md`
- Phase research: `.planning/phases/05-end-to-end-observability-and-run-history/05-RESEARCH.md`

**Steps**
1. Load `.planning/phases/05-end-to-end-observability-and-run-history/05-RESEARCH.md` and use it as a reference while executing this task.
2. If a phase context file is added later, load it and treat it as the phase vision before implementation.
3. Execute Task 1 action: define canonical `RunEventSchema` and related types for required correlation/event fields and payload safety metadata; export parsers/helpers via shared contracts surface.
4. Run task verification checks one-by-one: run `npm run test -- src/tests/frontend-api/run-events.contracts.test.ts` and confirm valid parse / malformed reject behavior.
5. Do not mark this task complete until done condition is satisfied: one runtime-validated RunEvent contract exists with complete payload slots and safety markers.
6. Write `.loop-commit-msg` with exactly one non-empty line: `05-01-task1`.
7. Update `.planning/STATE.md` with `phase=05-end-to-end-observability-and-run-history` / `plan=05-01-add-full-tool-payload-rendering-in-ui` / `task=1` / `status=implemented`.

## Section 33 — 05-end-to-end-observability-and-run-history — 05-01-add-full-tool-payload-rendering-in-ui — Task 2 (Execution)

**Required Inputs**
- Plan: `.planning/phases/05-end-to-end-observability-and-run-history/05-01-add-full-tool-payload-rendering-in-ui-PLAN.md`
- Phase research: `.planning/phases/05-end-to-end-observability-and-run-history/05-RESEARCH.md`

**Steps**
1. Load `.planning/phases/05-end-to-end-observability-and-run-history/05-RESEARCH.md` and use it as a reference while executing this task.
2. If a phase context file is added later, load it and treat it as the phase vision before implementation.
3. Execute Task 2 action: implement timeline + payload inspector UI to render full tool input/output for success/failure events, with visible redaction/truncation indicators and deterministic `event_seq` ordering.
4. Run task verification checks one-by-one: run `npm run dev:frontend`, execute one run with at least one success and one failure path, and confirm complete payload sections and safety indicators render correctly.
5. Do not mark this task complete until done condition is satisfied: user can inspect per-tool input/output payloads from timeline without switching views.
6. Write `.loop-commit-msg` with exactly one non-empty line: `05-01-task2`.
7. Update `.planning/STATE.md` with `phase=05-end-to-end-observability-and-run-history` / `plan=05-01-add-full-tool-payload-rendering-in-ui` / `task=2` / `status=implemented`.

## Section 34 — 05-end-to-end-observability-and-run-history — 05-01-add-full-tool-payload-rendering-in-ui — Task 3 (Execution)

**Required Inputs**
- Plan: `.planning/phases/05-end-to-end-observability-and-run-history/05-01-add-full-tool-payload-rendering-in-ui-PLAN.md`
- Phase research: `.planning/phases/05-end-to-end-observability-and-run-history/05-RESEARCH.md`

**Steps**
1. Load `.planning/phases/05-end-to-end-observability-and-run-history/05-RESEARCH.md` and use it as a reference while executing this task.
2. If a phase context file is added later, load it and treat it as the phase vision before implementation.
3. Execute Task 3 action: add contract/safety regression tests for schema acceptance/rejection, success/failure payload rendering availability, and secret redaction/truncation invariants.
4. Run task verification checks one-by-one: run `npm run test -- src/tests/frontend-api/run-events.contracts.test.ts`.
5. Do not mark this task complete until done condition is satisfied: tests prevent regressions in payload visibility, schema parity, and secret-safety behavior.
6. Write `.loop-commit-msg` with exactly one non-empty line: `05-01-task3`.
7. Update `.planning/STATE.md` with `phase=05-end-to-end-observability-and-run-history` / `plan=05-01-add-full-tool-payload-rendering-in-ui` / `task=3` / `status=implemented`.

## Section 35 — 05-end-to-end-observability-and-run-history — 05-01-add-full-tool-payload-rendering-in-ui (Summary)

**Required Inputs**
- Plan: `.planning/phases/05-end-to-end-observability-and-run-history/05-01-add-full-tool-payload-rendering-in-ui-PLAN.md`
- Phase research: `.planning/phases/05-end-to-end-observability-and-run-history/05-RESEARCH.md`

**Steps**
1. Create `.planning/phases/05-end-to-end-observability-and-run-history/05-01-SUMMARY.md` by following `## Summary Creation Instructions` in this file.
2. Write `.loop-commit-msg` with exactly one non-empty line: `05-01-summary`.

## Section 36 — 05-end-to-end-observability-and-run-history — 05-02-emit-and-correlate-structured-backend-observability-logs — Task 1 (Execution)

**Required Inputs**
- Plan: `.planning/phases/05-end-to-end-observability-and-run-history/05-02-emit-and-correlate-structured-backend-observability-logs-PLAN.md`
- Phase research: `.planning/phases/05-end-to-end-observability-and-run-history/05-RESEARCH.md`

**Steps**
1. Load `.planning/phases/05-end-to-end-observability-and-run-history/05-RESEARCH.md` and use it as a reference while executing this task.
2. If a phase context file is added later, load it and treat it as the phase vision before implementation.
3. Execute Task 1 action: implement run-scoped context with AsyncLocalStorage for `run_id` and monotonic `event_seq`, and wire initialization at run request entrypoint.
4. Run task verification checks one-by-one: run `npm run test -- src/tests/frontend-api/observability-correlation.test.ts` and confirm non-empty run IDs, strictly increasing event sequence, and no duplicate pair keys.
5. Do not mark this task complete until done condition is satisfied: correlation keys are deterministic across run lifecycle/tool events without manual threading.
6. Write `.loop-commit-msg` with exactly one non-empty line: `05-02-task1`.
7. Update `.planning/STATE.md` with `phase=05-end-to-end-observability-and-run-history` / `plan=05-02-emit-and-correlate-structured-backend-observability-logs` / `task=1` / `status=implemented`.

## Section 37 — 05-end-to-end-observability-and-run-history — 05-02-emit-and-correlate-structured-backend-observability-logs — Task 2 (Execution)

**Required Inputs**
- Plan: `.planning/phases/05-end-to-end-observability-and-run-history/05-02-emit-and-correlate-structured-backend-observability-logs-PLAN.md`
- Phase research: `.planning/phases/05-end-to-end-observability-and-run-history/05-RESEARCH.md`

**Steps**
1. Load `.planning/phases/05-end-to-end-observability-and-run-history/05-RESEARCH.md` and use it as a reference while executing this task.
2. If a phase context file is added later, load it and treat it as the phase vision before implementation.
3. Execute Task 2 action: create structured observability logger for lifecycle/tool events aligned to RunEvent contract, with secret redaction and payload truncation before emission, and instrument search/fetch routes.
4. Run task verification checks one-by-one: run `npm run test -- src/tests/frontend-api/observability-correlation.test.ts` and confirm expected event types, correlation fields, and no secret leaks.
5. Do not mark this task complete until done condition is satisfied: backend emits safe structured correlation-ready tool events for both search and fetch flows.
6. Write `.loop-commit-msg` with exactly one non-empty line: `05-02-task2`.
7. Update `.planning/STATE.md` with `phase=05-end-to-end-observability-and-run-history` / `plan=05-02-emit-and-correlate-structured-backend-observability-logs` / `task=2` / `status=implemented`.

## Section 38 — 05-end-to-end-observability-and-run-history — 05-02-emit-and-correlate-structured-backend-observability-logs — Task 3 (Execution)

**Required Inputs**
- Plan: `.planning/phases/05-end-to-end-observability-and-run-history/05-02-emit-and-correlate-structured-backend-observability-logs-PLAN.md`
- Phase research: `.planning/phases/05-end-to-end-observability-and-run-history/05-RESEARCH.md`

**Steps**
1. Load `.planning/phases/05-end-to-end-observability-and-run-history/05-RESEARCH.md` and use it as a reference while executing this task.
2. If a phase context file is added later, load it and treat it as the phase vision before implementation.
3. Execute Task 3 action: configure backend Docker logging for structured JSON/timestamps/rotation and enforce UI-log parity checks by (`run_id`, `event_seq`, `event_type`).
4. Run task verification checks one-by-one: run `docker compose up -d backend`, `docker compose logs --timestamps backend`, and `npm run test -- src/tests/frontend-api/observability-correlation.test.ts`.
5. Do not mark this task complete until done condition is satisfied: structured backend logs are retrievable and each frontend tool event correlates to exactly one backend log event.
6. Write `.loop-commit-msg` with exactly one non-empty line: `05-02-task3`.
7. Update `.planning/STATE.md` with `phase=05-end-to-end-observability-and-run-history` / `plan=05-02-emit-and-correlate-structured-backend-observability-logs` / `task=3` / `status=implemented`.

## Section 39 — 05-end-to-end-observability-and-run-history — 05-02-emit-and-correlate-structured-backend-observability-logs (Summary)

**Required Inputs**
- Plan: `.planning/phases/05-end-to-end-observability-and-run-history/05-02-emit-and-correlate-structured-backend-observability-logs-PLAN.md`
- Phase research: `.planning/phases/05-end-to-end-observability-and-run-history/05-RESEARCH.md`

**Steps**
1. Create `.planning/phases/05-end-to-end-observability-and-run-history/05-02-SUMMARY.md` by following `## Summary Creation Instructions` in this file.
2. Write `.loop-commit-msg` with exactly one non-empty line: `05-02-summary`.

## Section 40 — 05-end-to-end-observability-and-run-history — 05-03-finalize-run-history-presentation-with-answer-and-tool-trace — Task 1 (Execution)

**Required Inputs**
- Plan: `.planning/phases/05-end-to-end-observability-and-run-history/05-03-finalize-run-history-presentation-with-answer-and-tool-trace-PLAN.md`
- Phase research: `.planning/phases/05-end-to-end-observability-and-run-history/05-RESEARCH.md`

**Steps**
1. Load `.planning/phases/05-end-to-end-observability-and-run-history/05-RESEARCH.md` and use it as a reference while executing this task.
2. If a phase context file is added later, load it and treat it as the phase vision before implementation.
3. Execute Task 1 action: implement bounded run-history store keyed by `run_id`, preserving final answer + ordered tool events, monotonic `event_seq` semantics, duplicate handling, and retention limits with explicit truncation metadata.
4. Run task verification checks one-by-one: run `npm run test -- src/tests/frontend-api/run-history.integration.test.ts`.
5. Do not mark this task complete until done condition is satisfied: run history is deterministic, bounded, and complete for answer + trace rendering.
6. Write `.loop-commit-msg` with exactly one non-empty line: `05-03-task1`.
7. Update `.planning/STATE.md` with `phase=05-end-to-end-observability-and-run-history` / `plan=05-03-finalize-run-history-presentation-with-answer-and-tool-trace` / `task=1` / `status=implemented`.

## Section 41 — 05-end-to-end-observability-and-run-history — 05-03-finalize-run-history-presentation-with-answer-and-tool-trace — Task 2 (Execution)

**Required Inputs**
- Plan: `.planning/phases/05-end-to-end-observability-and-run-history/05-03-finalize-run-history-presentation-with-answer-and-tool-trace-PLAN.md`
- Phase research: `.planning/phases/05-end-to-end-observability-and-run-history/05-RESEARCH.md`

**Steps**
1. Load `.planning/phases/05-end-to-end-observability-and-run-history/05-RESEARCH.md` and use it as a reference while executing this task.
2. If a phase context file is added later, load it and treat it as the phase vision before implementation.
3. Execute Task 2 action: add run-history list/detail API endpoints and integrate with server, returning final answer + ordered timeline payloads aligned to established RunEvent/correlation contracts.
4. Run task verification checks one-by-one: run `npm run test -- src/tests/frontend-api/run-history.integration.test.ts` for populated and empty-history states.
5. Do not mark this task complete until done condition is satisfied: stable per-run history API returns final answer and full trace in one flow.
6. Write `.loop-commit-msg` with exactly one non-empty line: `05-03-task2`.
7. Update `.planning/STATE.md` with `phase=05-end-to-end-observability-and-run-history` / `plan=05-03-finalize-run-history-presentation-with-answer-and-tool-trace` / `task=2` / `status=implemented`.

## Section 42 — 05-end-to-end-observability-and-run-history — 05-03-finalize-run-history-presentation-with-answer-and-tool-trace — Task 3 (Execution)

**Required Inputs**
- Plan: `.planning/phases/05-end-to-end-observability-and-run-history/05-03-finalize-run-history-presentation-with-answer-and-tool-trace-PLAN.md`
- Phase research: `.planning/phases/05-end-to-end-observability-and-run-history/05-RESEARCH.md`

**Steps**
1. Load `.planning/phases/05-end-to-end-observability-and-run-history/05-RESEARCH.md` and use it as a reference while executing this task.
2. If a phase context file is added later, load it and treat it as the phase vision before implementation.
3. Execute Task 3 action: finalize cohesive UI flow that co-locates run selection, final answer, ordered timeline, and payload inspector; add integration tests for answer visibility, full trace presence, ordering stability, and bounded/truncated entries.
4. Run task verification checks one-by-one: run `npm run test -- src/tests/frontend-api/run-history.integration.test.ts`, then manually verify one active and one historical run with `npm run dev:frontend`.
5. Do not mark this task complete until done condition is satisfied: user can debug a run end-to-end in one cohesive UI flow.
6. Write `.loop-commit-msg` with exactly one non-empty line: `05-03-task3`.
7. Update `.planning/STATE.md` with `phase=05-end-to-end-observability-and-run-history` / `plan=05-03-finalize-run-history-presentation-with-answer-and-tool-trace` / `task=3` / `status=implemented`.

## Section 43 — 05-end-to-end-observability-and-run-history — 05-03-finalize-run-history-presentation-with-answer-and-tool-trace (Summary)

**Required Inputs**
- Plan: `.planning/phases/05-end-to-end-observability-and-run-history/05-03-finalize-run-history-presentation-with-answer-and-tool-trace-PLAN.md`
- Phase research: `.planning/phases/05-end-to-end-observability-and-run-history/05-RESEARCH.md`

**Steps**
1. Create `.planning/phases/05-end-to-end-observability-and-run-history/05-03-SUMMARY.md` by following `## Summary Creation Instructions` in this file.
2. Because this summary completes Phase 05, include the roadmap/state completion update in this summary section while still using a summary commit subject.
3. Write `.loop-commit-msg` with exactly one non-empty line: `05-03-summary`.
