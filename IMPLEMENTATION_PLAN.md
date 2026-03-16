Tasks are in **required implementation order** (1...n). Each section = one context window. Complete one section at a time.
Current section to work on: section 39. (move +1 after each turn)

## Summary Creation Instructions

### Ralph Loop Commit Contract (Required)
- The executor must **not** run `git commit` or `git push` directly.
- `.loop-commit-msg` must contain exactly one non-empty line.
- Section commit subjects must use exactly one of:
  - Task sections: `{phase}-{plan}-task{task-number}`
  - Summary sections: `{phase}-{plan}-summary`

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

## Section 1 — 01-core-retrieval-engine — 01-01 — Task 1 (Execution)
**Required inputs**
- Plan file: `.planning/phases/01-core-retrieval-engine/01-01-foundation-and-contracts-PLAN.md`
- Phase research: `.planning/phases/01-core-retrieval-engine/01-RESEARCH.md`

**Steps**
1. Load `.planning/phases/01-core-retrieval-engine/01-RESEARCH.md` and use it as implementation reference.
2. Execute only Task 1 action: bootstrap Node 24 + TypeScript workspace, scripts/dependencies, `src/sdk/index.ts` export surface, and baseline `src/tests/setup.test.ts`.
3. Run verify checks one by one: `npm install && npm run typecheck && npm run test -- src/tests/setup.test.ts`.
4. Confirm done condition: repo installs, typechecks, and baseline tests run with stable SDK export surface.
5. Do not mark task complete until the done condition is satisfied.
6. Write `.loop-commit-msg` with exactly one non-empty line: `01-01-task1`.
7. Update `.planning/STATE.md` with `phase=01-core-retrieval-engine` / `plan=01-01` / `task=1` / `status=implemented`.

## Section 2 — 01-core-retrieval-engine — 01-01 — Task 2 (Execution)
**Required inputs**
- Plan file: `.planning/phases/01-core-retrieval-engine/01-01-foundation-and-contracts-PLAN.md`
- Phase research: `.planning/phases/01-core-retrieval-engine/01-RESEARCH.md`

**Steps**
1. Load `.planning/phases/01-core-retrieval-engine/01-RESEARCH.md` and use it as implementation reference.
2. Execute only Task 2 action: create strict zod contracts/types for search/fetch inputs/outputs and normalization helpers for canonical defaults.
3. Run verify checks one by one: `npm run test -- src/tests/setup.test.ts`.
4. Confirm done condition: public contract source of truth exists for CORE-01/CORE-02 and is importable by adapters and SDK methods.
5. Do not mark task complete until the done condition is satisfied.
6. Write `.loop-commit-msg` with exactly one non-empty line: `01-01-task2`.
7. Update `.planning/STATE.md` with `phase=01-core-retrieval-engine` / `plan=01-01` / `task=2` / `status=implemented`.

## Section 3 — 01-core-retrieval-engine — 01-01 (Summary)
**Required inputs**
- Plan file: `.planning/phases/01-core-retrieval-engine/01-01-foundation-and-contracts-PLAN.md`
- Phase research: `.planning/phases/01-core-retrieval-engine/01-RESEARCH.md`

**Steps**
1. Create `.planning/phases/01-core-retrieval-engine/01-01-SUMMARY.md` by following `## Summary Creation Instructions` in this file.
2. Write `.loop-commit-msg` with exactly one non-empty line: `01-01-summary`.

## Section 4 — 01-core-retrieval-engine — 01-02 — Task 1 (Execution)
**Required inputs**
- Plan file: `.planning/phases/01-core-retrieval-engine/01-02-search-serper-slice-PLAN.md`
- Phase research: `.planning/phases/01-core-retrieval-engine/01-RESEARCH.md`

**Steps**
1. Load `.planning/phases/01-core-retrieval-engine/01-RESEARCH.md` and use it as implementation reference.
2. Execute only Task 1 action: implement bounded Serper transport with timeout/retry and adapter-boundary payload validation.
3. Run verify checks one by one: `npm run test -- src/tests/search/search.integration.test.ts` with mocked 429/5xx retry and non-retryable 4xx abort cases.
4. Confirm done condition: Serper client performs deterministic bounded retries and returns adapter-internal payload for mapping.
5. Do not mark task complete until the done condition is satisfied.
6. Write `.loop-commit-msg` with exactly one non-empty line: `01-02-task1`.
7. Update `.planning/STATE.md` with `phase=01-core-retrieval-engine` / `plan=01-02` / `task=1` / `status=implemented`.

## Section 5 — 01-core-retrieval-engine — 01-02 — Task 2 (Execution)
**Required inputs**
- Plan file: `.planning/phases/01-core-retrieval-engine/01-02-search-serper-slice-PLAN.md`
- Phase research: `.planning/phases/01-core-retrieval-engine/01-RESEARCH.md`

**Steps**
1. Load `.planning/phases/01-core-retrieval-engine/01-RESEARCH.md` and use it as implementation reference.
2. Execute only Task 2 action: implement deterministic `organic[]` mapping to normalized search contract with stable rank metadata and URL filtering.
3. Run verify checks one by one: `npm run test -- src/tests/search/serper-mapper.test.ts`.
4. Confirm done condition: equivalent provider payloads map to identical normalized outputs with stable rank metadata.
5. Do not mark task complete until the done condition is satisfied.
6. Write `.loop-commit-msg` with exactly one non-empty line: `01-02-task2`.
7. Update `.planning/STATE.md` with `phase=01-core-retrieval-engine` / `plan=01-02` / `task=2` / `status=implemented`.

## Section 6 — 01-core-retrieval-engine — 01-02 — Task 3 (Execution)
**Required inputs**
- Plan file: `.planning/phases/01-core-retrieval-engine/01-02-search-serper-slice-PLAN.md`
- Phase research: `.planning/phases/01-core-retrieval-engine/01-RESEARCH.md`

**Steps**
1. Load `.planning/phases/01-core-retrieval-engine/01-RESEARCH.md` and use it as implementation reference.
2. Execute only Task 3 action: wire full SDK `search(...)` orchestration (parse input, call client, map, validate output) and integration tests.
3. Run verify checks one by one: `npm run test -- src/tests/search/search.integration.test.ts` then `npm run typecheck`.
4. Confirm done condition: `search(query, options)` satisfies CORE-01 with deterministic normalized outputs and provider payload isolation.
5. Do not mark task complete until the done condition is satisfied.
6. Write `.loop-commit-msg` with exactly one non-empty line: `01-02-task3`.
7. Update `.planning/STATE.md` with `phase=01-core-retrieval-engine` / `plan=01-02` / `task=3` / `status=implemented`.

## Section 7 — 01-core-retrieval-engine — 01-02 (Summary)
**Required inputs**
- Plan file: `.planning/phases/01-core-retrieval-engine/01-02-search-serper-slice-PLAN.md`
- Phase research: `.planning/phases/01-core-retrieval-engine/01-RESEARCH.md`

**Steps**
1. Create `.planning/phases/01-core-retrieval-engine/01-02-SUMMARY.md` by following `## Summary Creation Instructions` in this file.
2. Write `.loop-commit-msg` with exactly one non-empty line: `01-02-summary`.

## Section 8 — 01-core-retrieval-engine — 01-03 — Task 1 (Execution)
**Required inputs**
- Plan file: `.planning/phases/01-core-retrieval-engine/01-03-fetch-http-first-slice-PLAN.md`
- Phase research: `.planning/phases/01-core-retrieval-engine/01-RESEARCH.md`

**Steps**
1. Load `.planning/phases/01-core-retrieval-engine/01-RESEARCH.md` and use it as implementation reference.
2. Execute only Task 1 action: build robots/politeness gate and HTTP worker with explicit typed states and bounded timeout/retry.
3. Run verify checks one by one: `npm run test -- src/tests/fetch/fetch.unit.test.ts`.
4. Confirm done condition: deterministic preflight gating and HTTP retrieval behavior exist with explicit typed outcomes.
5. Do not mark task complete until the done condition is satisfied.
6. Write `.loop-commit-msg` with exactly one non-empty line: `01-03-task1`.
7. Update `.planning/STATE.md` with `phase=01-core-retrieval-engine` / `plan=01-03` / `task=1` / `status=implemented`.

## Section 9 — 01-core-retrieval-engine — 01-03 — Task 2 (Execution)
**Required inputs**
- Plan file: `.planning/phases/01-core-retrieval-engine/01-03-fetch-http-first-slice-PLAN.md`
- Phase research: `.planning/phases/01-core-retrieval-engine/01-RESEARCH.md`

**Steps**
1. Load `.planning/phases/01-core-retrieval-engine/01-RESEARCH.md` and use it as implementation reference.
2. Execute only Task 2 action: implement extraction + HTTP-first orchestrator and replace placeholder SDK `fetch.ts` wiring with explicit fallback reasons.
3. Run verify checks one by one: `npm run test -- src/tests/fetch/fetch.unit.test.ts`.
4. Confirm done condition: `fetch(url, options)` returns clean consistent shape and enforces HTTP-first orchestration.
5. Do not mark task complete until the done condition is satisfied.
6. Write `.loop-commit-msg` with exactly one non-empty line: `01-03-task2`.
7. Update `.planning/STATE.md` with `phase=01-core-retrieval-engine` / `plan=01-03` / `task=2` / `status=implemented`.

## Section 10 — 01-core-retrieval-engine — 01-03 — Task 3 (Execution)
**Required inputs**
- Plan file: `.planning/phases/01-core-retrieval-engine/01-03-fetch-http-first-slice-PLAN.md`
- Phase research: `.planning/phases/01-core-retrieval-engine/01-RESEARCH.md`

**Steps**
1. Load `.planning/phases/01-core-retrieval-engine/01-RESEARCH.md` and use it as implementation reference.
2. Execute only Task 3 action: add fixture-based repeated-run stability tests for deterministic fetch structure and fallback reasons.
3. Run verify checks one by one: `npm run test -- src/tests/fetch/fetch.stability.test.ts && npm run typecheck && npm run build`.
4. Confirm done condition: CORE-02 plus fetch stability requirement verified through deterministic fixture tests.
5. Do not mark task complete until the done condition is satisfied.
6. Write `.loop-commit-msg` with exactly one non-empty line: `01-03-task3`.
7. Update `.planning/STATE.md` with `phase=01-core-retrieval-engine` / `plan=01-03` / `task=3` / `status=implemented`.

## Section 11 — 01-core-retrieval-engine — 01-03 (Summary)
**Required inputs**
- Plan file: `.planning/phases/01-core-retrieval-engine/01-03-fetch-http-first-slice-PLAN.md`
- Phase research: `.planning/phases/01-core-retrieval-engine/01-RESEARCH.md`

**Steps**
1. Create `.planning/phases/01-core-retrieval-engine/01-03-SUMMARY.md` by following `## Summary Creation Instructions` in this file.
2. Write `.loop-commit-msg` with exactly one non-empty line: `01-03-summary`.
3. Because this is the final plan in Phase 01, also update roadmap/state progress to reflect Phase 01 completion.

## Section 12 — 02-retrieval-controls-and-cost-tuning — 02-01 — Task 1 (Execution)
**Required inputs**
- Plan file: `.planning/phases/02-retrieval-controls-and-cost-tuning/02-01-retrieval-controls-foundation-PLAN.md`
- Phase research: `.planning/phases/02-retrieval-controls-and-cost-tuning/02-RESEARCH.md`

**Steps**
1. Load `.planning/phases/02-retrieval-controls-and-cost-tuning/02-RESEARCH.md` and use it as implementation reference.
2. Execute only Task 1 action: build shared retrieval controls resolver with deterministic defaults/bounds and provider-agnostic normalized output.
3. Run verify checks one by one: `npm run typecheck`.
4. Confirm done condition: single reusable RetrievalControls normalization source exists for search and fetch.
5. Do not mark task complete until the done condition is satisfied.
6. Write `.loop-commit-msg` with exactly one non-empty line: `02-01-task1`.
7. Update `.planning/STATE.md` with `phase=02-retrieval-controls-and-cost-tuning` / `plan=02-01` / `task=1` / `status=implemented`.

## Section 13 — 02-retrieval-controls-and-cost-tuning — 02-01 — Task 2 (Execution)
**Required inputs**
- Plan file: `.planning/phases/02-retrieval-controls-and-cost-tuning/02-01-retrieval-controls-foundation-PLAN.md`
- Phase research: `.planning/phases/02-retrieval-controls-and-cost-tuning/02-RESEARCH.md`

**Steps**
1. Load `.planning/phases/02-retrieval-controls-and-cost-tuning/02-RESEARCH.md` and use it as implementation reference.
2. Execute only Task 2 action: implement canonical domain scope normalization (dedupe/lowercase/conflict precedence exclude-wins) and wire into control resolution.
3. Run verify checks one by one: `npm run typecheck`.
4. Confirm done condition: canonical domain policy output is deterministic and suitable for query/post-filter enforcement.
5. Do not mark task complete until the done condition is satisfied.
6. Write `.loop-commit-msg` with exactly one non-empty line: `02-01-task2`.
7. Update `.planning/STATE.md` with `phase=02-retrieval-controls-and-cost-tuning` / `plan=02-01` / `task=2` / `status=implemented`.

## Section 14 — 02-retrieval-controls-and-cost-tuning — 02-01 — Task 3 (Execution)
**Required inputs**
- Plan file: `.planning/phases/02-retrieval-controls-and-cost-tuning/02-01-retrieval-controls-foundation-PLAN.md`
- Phase research: `.planning/phases/02-retrieval-controls-and-cost-tuning/02-RESEARCH.md`

**Steps**
1. Load `.planning/phases/02-retrieval-controls-and-cost-tuning/02-RESEARCH.md` and use it as implementation reference.
2. Execute only Task 3 action: add focused policy tests for defaults, bounds, freshness semantics, and domain canonicalization stability.
3. Run verify checks one by one: `npm run test -- src/core/policy/retrieval-controls.test.ts`.
4. Confirm done condition: policy behavior is executable-spec documented and safe for dependent plans.
5. Do not mark task complete until the done condition is satisfied.
6. Write `.loop-commit-msg` with exactly one non-empty line: `02-01-task3`.
7. Update `.planning/STATE.md` with `phase=02-retrieval-controls-and-cost-tuning` / `plan=02-01` / `task=3` / `status=implemented`.

## Section 15 — 02-retrieval-controls-and-cost-tuning — 02-01 (Summary)
**Required inputs**
- Plan file: `.planning/phases/02-retrieval-controls-and-cost-tuning/02-01-retrieval-controls-foundation-PLAN.md`
- Phase research: `.planning/phases/02-retrieval-controls-and-cost-tuning/02-RESEARCH.md`

**Steps**
1. Create `.planning/phases/02-retrieval-controls-and-cost-tuning/02-01-SUMMARY.md` by following `## Summary Creation Instructions` in this file.
2. Write `.loop-commit-msg` with exactly one non-empty line: `02-01-summary`.

## Section 16 — 02-retrieval-controls-and-cost-tuning — 02-02 — Task 1 (Execution)
**Required inputs**
- Plan file: `.planning/phases/02-retrieval-controls-and-cost-tuning/02-02-search-controls-and-serper-mapping-PLAN.md`
- Phase research: `.planning/phases/02-retrieval-controls-and-cost-tuning/02-RESEARCH.md`

**Steps**
1. Load `.planning/phases/02-retrieval-controls-and-cost-tuning/02-RESEARCH.md` and use it as implementation reference.
2. Execute only Task 1 action: extend search contracts/SDK flow for normalized controls and deterministic defaults.
3. Run verify checks one by one: `npm run typecheck`.
4. Confirm done condition: search entrypoint accepts controls with deterministic defaults via shared policy output.
5. Do not mark task complete until the done condition is satisfied.
6. Write `.loop-commit-msg` with exactly one non-empty line: `02-02-task1`.
7. Update `.planning/STATE.md` with `phase=02-retrieval-controls-and-cost-tuning` / `plan=02-02` / `task=1` / `status=implemented`.

## Section 17 — 02-retrieval-controls-and-cost-tuning — 02-02 — Task 2 (Execution)
**Required inputs**
- Plan file: `.planning/phases/02-retrieval-controls-and-cost-tuning/02-02-search-controls-and-serper-mapping-PLAN.md`
- Phase research: `.planning/phases/02-retrieval-controls-and-cost-tuning/02-RESEARCH.md`

**Steps**
1. Load `.planning/phases/02-retrieval-controls-and-cost-tuning/02-RESEARCH.md` and use it as implementation reference.
2. Execute only Task 2 action: map normalized controls to Serper request and enforce post-result domain filtering with timeout control.
3. Run verify checks one by one: `npm run test -- src/tests/search-controls.integration.test.ts`.
4. Confirm done condition: controls enforced pre/post provider call and provider-specific details remain adapter-internal.
5. Do not mark task complete until the done condition is satisfied.
6. Write `.loop-commit-msg` with exactly one non-empty line: `02-02-task2`.
7. Update `.planning/STATE.md` with `phase=02-retrieval-controls-and-cost-tuning` / `plan=02-02` / `task=2` / `status=implemented`.

## Section 18 — 02-retrieval-controls-and-cost-tuning — 02-02 — Task 3 (Execution)
**Required inputs**
- Plan file: `.planning/phases/02-retrieval-controls-and-cost-tuning/02-02-search-controls-and-serper-mapping-PLAN.md`
- Phase research: `.planning/phases/02-retrieval-controls-and-cost-tuning/02-RESEARCH.md`

**Steps**
1. Load `.planning/phases/02-retrieval-controls-and-cost-tuning/02-RESEARCH.md` and use it as implementation reference.
2. Execute only Task 3 action: add integration tests for maxResults, timeout, domain include/exclude, locale defaults, and freshness mapping.
3. Run verify checks one by one: `npm run test -- src/tests/search-controls.integration.test.ts`.
4. Confirm done condition: CTRL-01/02/03 search requirements are validated by repeatable tests.
5. Do not mark task complete until the done condition is satisfied.
6. Write `.loop-commit-msg` with exactly one non-empty line: `02-02-task3`.
7. Update `.planning/STATE.md` with `phase=02-retrieval-controls-and-cost-tuning` / `plan=02-02` / `task=3` / `status=implemented`.

## Section 19 — 02-retrieval-controls-and-cost-tuning — 02-02 (Summary)
**Required inputs**
- Plan file: `.planning/phases/02-retrieval-controls-and-cost-tuning/02-02-search-controls-and-serper-mapping-PLAN.md`
- Phase research: `.planning/phases/02-retrieval-controls-and-cost-tuning/02-RESEARCH.md`

**Steps**
1. Create `.planning/phases/02-retrieval-controls-and-cost-tuning/02-02-SUMMARY.md` by following `## Summary Creation Instructions` in this file.
2. Write `.loop-commit-msg` with exactly one non-empty line: `02-02-summary`.

## Section 20 — 02-retrieval-controls-and-cost-tuning — 02-03 — Task 1 (Execution)
**Required inputs**
- Plan file: `.planning/phases/02-retrieval-controls-and-cost-tuning/02-03-fetch-cache-policy-and-freshness-PLAN.md`
- Phase research: `.planning/phases/02-retrieval-controls-and-cost-tuning/02-RESEARCH.md`

**Steps**
1. Load `.planning/phases/02-retrieval-controls-and-cost-tuning/02-RESEARCH.md` and use it as implementation reference.
2. Execute only Task 1 action: add fetch cache controls to contracts and SDK with explicit precedence (`fresh=true` bypasses reads).
3. Run verify checks one by one: `npm run typecheck`.
4. Confirm done condition: fetch callers can pass cache controls and SDK applies deterministic precedence before retrieval.
5. Do not mark task complete until the done condition is satisfied.
6. Write `.loop-commit-msg` with exactly one non-empty line: `02-03-task1`.
7. Update `.planning/STATE.md` with `phase=02-retrieval-controls-and-cost-tuning` / `plan=02-03` / `task=1` / `status=implemented`.

## Section 21 — 02-retrieval-controls-and-cost-tuning — 02-03 — Task 2 (Execution)
**Required inputs**
- Plan file: `.planning/phases/02-retrieval-controls-and-cost-tuning/02-03-fetch-cache-policy-and-freshness-PLAN.md`
- Phase research: `.planning/phases/02-retrieval-controls-and-cost-tuning/02-RESEARCH.md`

**Steps**
1. Load `.planning/phases/02-retrieval-controls-and-cost-tuning/02-RESEARCH.md` and use it as implementation reference.
2. Execute only Task 2 action: implement bounded fetch cache utility with normalized keying, maxAge checks, force-fresh bypass, and write-after-fetch behavior.
3. Run verify checks one by one: `npm run test -- src/core/cache/fetch-cache.test.ts`.
4. Confirm done condition: cache behavior is deterministic, bounded, and reusable from fetch orchestration.
5. Do not mark task complete until the done condition is satisfied.
6. Write `.loop-commit-msg` with exactly one non-empty line: `02-03-task2`.
7. Update `.planning/STATE.md` with `phase=02-retrieval-controls-and-cost-tuning` / `plan=02-03` / `task=2` / `status=implemented`.

## Section 22 — 02-retrieval-controls-and-cost-tuning — 02-03 — Task 3 (Execution)
**Required inputs**
- Plan file: `.planning/phases/02-retrieval-controls-and-cost-tuning/02-03-fetch-cache-policy-and-freshness-PLAN.md`
- Phase research: `.planning/phases/02-retrieval-controls-and-cost-tuning/02-RESEARCH.md`

**Steps**
1. Load `.planning/phases/02-retrieval-controls-and-cost-tuning/02-RESEARCH.md` and use it as implementation reference.
2. Execute only Task 3 action: add integration tests for hit/miss/stale/fresh bypass semantics and precedence.
3. Run verify checks one by one: `npm run test -- src/tests/fetch-controls.integration.test.ts`.
4. Confirm done condition: REL-03 behavior is validated for fetch with repeatable tests.
5. Do not mark task complete until the done condition is satisfied.
6. Write `.loop-commit-msg` with exactly one non-empty line: `02-03-task3`.
7. Update `.planning/STATE.md` with `phase=02-retrieval-controls-and-cost-tuning` / `plan=02-03` / `task=3` / `status=implemented`.

## Section 23 — 02-retrieval-controls-and-cost-tuning — 02-03 (Summary)
**Required inputs**
- Plan file: `.planning/phases/02-retrieval-controls-and-cost-tuning/02-03-fetch-cache-policy-and-freshness-PLAN.md`
- Phase research: `.planning/phases/02-retrieval-controls-and-cost-tuning/02-RESEARCH.md`

**Steps**
1. Create `.planning/phases/02-retrieval-controls-and-cost-tuning/02-03-SUMMARY.md` by following `## Summary Creation Instructions` in this file.
2. Write `.loop-commit-msg` with exactly one non-empty line: `02-03-summary`.
3. Because this is the final plan in Phase 02, also update roadmap/state progress to reflect Phase 02 completion.

## Section 24 — 03-reliability-and-usage-transparency — 03-01 — Task 1 (Execution)
**Required inputs**
- Plan file: `.planning/phases/03-reliability-and-usage-transparency/03-01-shared-reliability-contracts-PLAN.md`
- Phase research: `.planning/phases/03-reliability-and-usage-transparency/03-RESEARCH.md`

**Steps**
1. Load `.planning/phases/03-reliability-and-usage-transparency/03-RESEARCH.md` and use it as implementation reference.
2. Execute only Task 1 action: define canonical typed SDK error taxonomy and deterministic classifier.
3. Run verify checks one by one: `npm run typecheck` and map-assertions in `src/tests/core/reliability/execute-with-retry.test.ts`.
4. Confirm done condition: errors are actionable via stable discriminants and deterministic mapping.
5. Do not mark task complete until the done condition is satisfied.
6. Write `.loop-commit-msg` with exactly one non-empty line: `03-01-task1`.
7. Update `.planning/STATE.md` with `phase=03-reliability-and-usage-transparency` / `plan=03-01` / `task=1` / `status=implemented`.

## Section 25 — 03-reliability-and-usage-transparency — 03-01 — Task 2 (Execution)
**Required inputs**
- Plan file: `.planning/phases/03-reliability-and-usage-transparency/03-01-shared-reliability-contracts-PLAN.md`
- Phase research: `.planning/phases/03-reliability-and-usage-transparency/03-RESEARCH.md`

**Steps**
1. Load `.planning/phases/03-reliability-and-usage-transparency/03-RESEARCH.md` and use it as implementation reference.
2. Execute only Task 2 action: implement shared deterministic retry executor with Retry-After precedence and non-retryable short-circuit behavior.
3. Run verify checks one by one: `npm run test -- src/tests/core/reliability/execute-with-retry.test.ts`.
4. Confirm done condition: one shared deterministic retry path exists for search/fetch with standards-aligned rate-limit handling.
5. Do not mark task complete until the done condition is satisfied.
6. Write `.loop-commit-msg` with exactly one non-empty line: `03-01-task2`.
7. Update `.planning/STATE.md` with `phase=03-reliability-and-usage-transparency` / `plan=03-01` / `task=2` / `status=implemented`.

## Section 26 — 03-reliability-and-usage-transparency — 03-01 — Task 3 (Execution)
**Required inputs**
- Plan file: `.planning/phases/03-reliability-and-usage-transparency/03-01-shared-reliability-contracts-PLAN.md`
- Phase research: `.planning/phases/03-reliability-and-usage-transparency/03-RESEARCH.md`

**Steps**
1. Load `.planning/phases/03-reliability-and-usage-transparency/03-RESEARCH.md` and use it as implementation reference.
2. Execute only Task 3 action: add shared call metadata builder and wire required `meta` fields into search/fetch contracts.
3. Run verify checks one by one: `npm run test -- src/tests/core/telemetry/call-meta.test.ts && npm run typecheck`.
4. Confirm done condition: REL-02 metadata contract baseline exists for both primitives.
5. Do not mark task complete until the done condition is satisfied.
6. Write `.loop-commit-msg` with exactly one non-empty line: `03-01-task3`.
7. Update `.planning/STATE.md` with `phase=03-reliability-and-usage-transparency` / `plan=03-01` / `task=3` / `status=implemented`.

## Section 27 — 03-reliability-and-usage-transparency — 03-01 (Summary)
**Required inputs**
- Plan file: `.planning/phases/03-reliability-and-usage-transparency/03-01-shared-reliability-contracts-PLAN.md`
- Phase research: `.planning/phases/03-reliability-and-usage-transparency/03-RESEARCH.md`

**Steps**
1. Create `.planning/phases/03-reliability-and-usage-transparency/03-01-SUMMARY.md` by following `## Summary Creation Instructions` in this file.
2. Write `.loop-commit-msg` with exactly one non-empty line: `03-01-summary`.

## Section 28 — 03-reliability-and-usage-transparency — 03-02 — Task 1 (Execution)
**Required inputs**
- Plan file: `.planning/phases/03-reliability-and-usage-transparency/03-02-search-reliability-and-metadata-PLAN.md`
- Phase research: `.planning/phases/03-reliability-and-usage-transparency/03-RESEARCH.md`

**Steps**
1. Load `.planning/phases/03-reliability-and-usage-transparency/03-RESEARCH.md` and use it as implementation reference.
2. Execute only Task 1 action: route Serper calls through shared retry/error pipeline with deterministic 429/5xx behavior.
3. Run verify checks one by one: `npm run test -- src/tests/search/search.reliability.test.ts`.
4. Confirm done condition: search transport reliability is centralized, deterministic, and contract-stable.
5. Do not mark task complete until the done condition is satisfied.
6. Write `.loop-commit-msg` with exactly one non-empty line: `03-02-task1`.
7. Update `.planning/STATE.md` with `phase=03-reliability-and-usage-transparency` / `plan=03-02` / `task=1` / `status=implemented`.

## Section 29 — 03-reliability-and-usage-transparency — 03-02 — Task 2 (Execution)
**Required inputs**
- Plan file: `.planning/phases/03-reliability-and-usage-transparency/03-02-search-reliability-and-metadata-PLAN.md`
- Phase research: `.planning/phases/03-reliability-and-usage-transparency/03-RESEARCH.md`

**Steps**
1. Load `.planning/phases/03-reliability-and-usage-transparency/03-RESEARCH.md` and use it as implementation reference.
2. Execute only Task 2 action: emit search call metadata via shared telemetry builder while preserving normalized payload boundaries.
3. Run verify checks one by one: `npm run test -- src/tests/search/search.meta.test.ts && npm run typecheck`.
4. Confirm done condition: successful search responses expose stable inspectable metadata satisfying REL-02 for search.
5. Do not mark task complete until the done condition is satisfied.
6. Write `.loop-commit-msg` with exactly one non-empty line: `03-02-task2`.
7. Update `.planning/STATE.md` with `phase=03-reliability-and-usage-transparency` / `plan=03-02` / `task=2` / `status=implemented`.

## Section 30 — 03-reliability-and-usage-transparency — 03-02 — Task 3 (Execution)
**Required inputs**
- Plan file: `.planning/phases/03-reliability-and-usage-transparency/03-02-search-reliability-and-metadata-PLAN.md`
- Phase research: `.planning/phases/03-reliability-and-usage-transparency/03-RESEARCH.md`

**Steps**
1. Load `.planning/phases/03-reliability-and-usage-transparency/03-RESEARCH.md` and use it as implementation reference.
2. Execute only Task 3 action: validate full search reliability + metadata behavior across transient/non-retryable/success scenarios.
3. Run verify checks one by one: `npm run test -- src/tests/search/search.reliability.test.ts src/tests/search/search.meta.test.ts`.
4. Confirm done condition: REL-01 and REL-02 are verified for search at SDK boundary.
5. Do not mark task complete until the done condition is satisfied.
6. Write `.loop-commit-msg` with exactly one non-empty line: `03-02-task3`.
7. Update `.planning/STATE.md` with `phase=03-reliability-and-usage-transparency` / `plan=03-02` / `task=3` / `status=implemented`.

## Section 31 — 03-reliability-and-usage-transparency — 03-02 (Summary)
**Required inputs**
- Plan file: `.planning/phases/03-reliability-and-usage-transparency/03-02-search-reliability-and-metadata-PLAN.md`
- Phase research: `.planning/phases/03-reliability-and-usage-transparency/03-RESEARCH.md`

**Steps**
1. Create `.planning/phases/03-reliability-and-usage-transparency/03-02-SUMMARY.md` by following `## Summary Creation Instructions` in this file.
2. Write `.loop-commit-msg` with exactly one non-empty line: `03-02-summary`.

## Section 32 — 03-reliability-and-usage-transparency — 03-03 — Task 1 (Execution)
**Required inputs**
- Plan file: `.planning/phases/03-reliability-and-usage-transparency/03-03-fetch-reliability-and-metadata-PLAN.md`
- Phase research: `.planning/phases/03-reliability-and-usage-transparency/03-RESEARCH.md`

**Steps**
1. Load `.planning/phases/03-reliability-and-usage-transparency/03-RESEARCH.md` and use it as implementation reference.
2. Execute only Task 1 action: route fetch HTTP path through shared deterministic retry/error executor.
3. Run verify checks one by one: `npm run test -- src/tests/fetch/fetch.reliability.test.ts`.
4. Confirm done condition: fetch worker reliability is deterministic, bounded, and aligned to shared taxonomy.
5. Do not mark task complete until the done condition is satisfied.
6. Write `.loop-commit-msg` with exactly one non-empty line: `03-03-task1`.
7. Update `.planning/STATE.md` with `phase=03-reliability-and-usage-transparency` / `plan=03-03` / `task=1` / `status=implemented`.

## Section 33 — 03-reliability-and-usage-transparency — 03-03 — Task 2 (Execution)
**Required inputs**
- Plan file: `.planning/phases/03-reliability-and-usage-transparency/03-03-fetch-reliability-and-metadata-PLAN.md`
- Phase research: `.planning/phases/03-reliability-and-usage-transparency/03-RESEARCH.md`

**Steps**
1. Load `.planning/phases/03-reliability-and-usage-transparency/03-RESEARCH.md` and use it as implementation reference.
2. Execute only Task 2 action: propagate typed errors + metadata through fetch orchestrator and SDK responses.
3. Run verify checks one by one: `npm run test -- src/tests/fetch/fetch.meta.test.ts && npm run typecheck`.
4. Confirm done condition: successful `fetch(...)` returns stable metadata and failures are typed/actionable.
5. Do not mark task complete until the done condition is satisfied.
6. Write `.loop-commit-msg` with exactly one non-empty line: `03-03-task2`.
7. Update `.planning/STATE.md` with `phase=03-reliability-and-usage-transparency` / `plan=03-03` / `task=2` / `status=implemented`.

## Section 34 — 03-reliability-and-usage-transparency — 03-03 — Task 3 (Execution)
**Required inputs**
- Plan file: `.planning/phases/03-reliability-and-usage-transparency/03-03-fetch-reliability-and-metadata-PLAN.md`
- Phase research: `.planning/phases/03-reliability-and-usage-transparency/03-RESEARCH.md`

**Steps**
1. Load `.planning/phases/03-reliability-and-usage-transparency/03-RESEARCH.md` and use it as implementation reference.
2. Execute only Task 3 action: expand fetch reliability + metadata scenario coverage and keep deterministic assertions.
3. Run verify checks one by one: `npm run test -- src/tests/fetch/fetch.reliability.test.ts src/tests/fetch/fetch.meta.test.ts`.
4. Confirm done condition: REL-01/REL-02 are verified for fetch at SDK boundary.
5. Do not mark task complete until the done condition is satisfied.
6. Write `.loop-commit-msg` with exactly one non-empty line: `03-03-task3`.
7. Update `.planning/STATE.md` with `phase=03-reliability-and-usage-transparency` / `plan=03-03` / `task=3` / `status=implemented`.

## Section 35 — 03-reliability-and-usage-transparency — 03-03 (Summary)
**Required inputs**
- Plan file: `.planning/phases/03-reliability-and-usage-transparency/03-03-fetch-reliability-and-metadata-PLAN.md`
- Phase research: `.planning/phases/03-reliability-and-usage-transparency/03-RESEARCH.md`

**Steps**
1. Create `.planning/phases/03-reliability-and-usage-transparency/03-03-SUMMARY.md` by following `## Summary Creation Instructions` in this file.
2. Write `.loop-commit-msg` with exactly one non-empty line: `03-03-summary`.
3. Because this is the final plan in Phase 03, also update roadmap/state progress to reflect Phase 03 completion.

## Section 36 — 04-fetch-safety-and-compliance-guardrails — 04-01 — Task 1 (Execution)
**Required inputs**
- Plan file: `.planning/phases/04-fetch-safety-and-compliance-guardrails/04-01-safety-decision-contracts-PLAN.md`
- Phase research: `.planning/phases/04-fetch-safety-and-compliance-guardrails/04-RESEARCH.md`

**Steps**
1. Load `.planning/phases/04-fetch-safety-and-compliance-guardrails/04-RESEARCH.md` and use it as implementation reference.
2. Execute only Task 1 action: define typed safety/compliance contracts and wire fetch contract metadata fields.
3. Run verify checks one by one: `npm run typecheck`.
4. Confirm done condition: shared typed safety/compliance outcomes exist and are available to fetch orchestration.
5. Do not mark task complete until the done condition is satisfied.
6. Write `.loop-commit-msg` with exactly one non-empty line: `04-01-task1`.
7. Update `.planning/STATE.md` with `phase=04-fetch-safety-and-compliance-guardrails` / `plan=04-01` / `task=1` / `status=implemented`.

## Section 37 — 04-fetch-safety-and-compliance-guardrails — 04-01 — Task 2 (Execution)
**Required inputs**
- Plan file: `.planning/phases/04-fetch-safety-and-compliance-guardrails/04-01-safety-decision-contracts-PLAN.md`
- Phase research: `.planning/phases/04-fetch-safety-and-compliance-guardrails/04-RESEARCH.md`

**Steps**
1. Load `.planning/phases/04-fetch-safety-and-compliance-guardrails/04-RESEARCH.md` and use it as implementation reference.
2. Execute only Task 2 action: implement deterministic fail-closed URL preflight evaluator returning typed allow/deny decisions.
3. Run verify checks one by one: `npm run test -- src/tests/safety/url-policy.test.ts`.
4. Confirm done condition: preflight URL policy can deterministically allow/deny before network execution.
5. Do not mark task complete until the done condition is satisfied.
6. Write `.loop-commit-msg` with exactly one non-empty line: `04-01-task2`.
7. Update `.planning/STATE.md` with `phase=04-fetch-safety-and-compliance-guardrails` / `plan=04-01` / `task=2` / `status=implemented`.

## Section 38 — 04-fetch-safety-and-compliance-guardrails — 04-01 — Task 3 (Execution)
**Required inputs**
- Plan file: `.planning/phases/04-fetch-safety-and-compliance-guardrails/04-01-safety-decision-contracts-PLAN.md`
- Phase research: `.planning/phases/04-fetch-safety-and-compliance-guardrails/04-RESEARCH.md`

**Steps**
1. Load `.planning/phases/04-fetch-safety-and-compliance-guardrails/04-RESEARCH.md` and use it as implementation reference.
2. Execute only Task 3 action: map policy-deny decisions to typed public fetch errors/outcomes with machine-readable fields.
3. Run verify checks one by one: `npm run test -- src/tests/safety/url-policy.test.ts && npm run typecheck`.
4. Confirm done condition: policy denies surface as typed inspectable outcomes instead of opaque exceptions.
5. Do not mark task complete until the done condition is satisfied.
6. Write `.loop-commit-msg` with exactly one non-empty line: `04-01-task3`.
7. Update `.planning/STATE.md` with `phase=04-fetch-safety-and-compliance-guardrails` / `plan=04-01` / `task=3` / `status=implemented`.

## Section 39 — 04-fetch-safety-and-compliance-guardrails — 04-01 (Summary)
**Required inputs**
- Plan file: `.planning/phases/04-fetch-safety-and-compliance-guardrails/04-01-safety-decision-contracts-PLAN.md`
- Phase research: `.planning/phases/04-fetch-safety-and-compliance-guardrails/04-RESEARCH.md`

**Steps**
1. Create `.planning/phases/04-fetch-safety-and-compliance-guardrails/04-01-SUMMARY.md` by following `## Summary Creation Instructions` in this file.
2. Write `.loop-commit-msg` with exactly one non-empty line: `04-01-summary`.

## Section 40 — 04-fetch-safety-and-compliance-guardrails — 04-02 — Task 1 (Execution)
**Required inputs**
- Plan file: `.planning/phases/04-fetch-safety-and-compliance-guardrails/04-02-ssrf-network-guardrails-PLAN.md`
- Phase research: `.planning/phases/04-fetch-safety-and-compliance-guardrails/04-RESEARCH.md`

**Steps**
1. Load `.planning/phases/04-fetch-safety-and-compliance-guardrails/04-RESEARCH.md` and use it as implementation reference.
2. Execute only Task 1 action: build SSRF IP classification policy for private/internal/reserved ranges with typed deny reasons.
3. Run verify checks one by one: `npm run test -- src/tests/safety/ssrf-guardrails.test.ts`.
4. Confirm done condition: deterministic IP safety policy identifies disallowed ranges with typed outcomes.
5. Do not mark task complete until the done condition is satisfied.
6. Write `.loop-commit-msg` with exactly one non-empty line: `04-02-task1`.
7. Update `.planning/STATE.md` with `phase=04-fetch-safety-and-compliance-guardrails` / `plan=04-02` / `task=1` / `status=implemented`.

## Section 41 — 04-fetch-safety-and-compliance-guardrails — 04-02 — Task 2 (Execution)
**Required inputs**
- Plan file: `.planning/phases/04-fetch-safety-and-compliance-guardrails/04-02-ssrf-network-guardrails-PLAN.md`
- Phase research: `.planning/phases/04-fetch-safety-and-compliance-guardrails/04-RESEARCH.md`

**Steps**
1. Load `.planning/phases/04-fetch-safety-and-compliance-guardrails/04-RESEARCH.md` and use it as implementation reference.
2. Execute only Task 2 action: implement DNS resolve-and-classify gate denying any disallowed resolved candidate and handling resolver failures explicitly.
3. Run verify checks one by one: `npm run test -- src/tests/safety/ssrf-guardrails.test.ts`.
4. Confirm done condition: hostname network preflight is deterministic before connection attempts.
5. Do not mark task complete until the done condition is satisfied.
6. Write `.loop-commit-msg` with exactly one non-empty line: `04-02-task2`.
7. Update `.planning/STATE.md` with `phase=04-fetch-safety-and-compliance-guardrails` / `plan=04-02` / `task=2` / `status=implemented`.

## Section 42 — 04-fetch-safety-and-compliance-guardrails — 04-02 — Task 3 (Execution)
**Required inputs**
- Plan file: `.planning/phases/04-fetch-safety-and-compliance-guardrails/04-02-ssrf-network-guardrails-PLAN.md`
- Phase research: `.planning/phases/04-fetch-safety-and-compliance-guardrails/04-RESEARCH.md`

**Steps**
1. Load `.planning/phases/04-fetch-safety-and-compliance-guardrails/04-RESEARCH.md` and use it as implementation reference.
2. Execute only Task 3 action: enforce redirect-hop safety revalidation with hop cap and explicit unsafe-redirect deny outcomes.
3. Run verify checks one by one: `npm run test -- src/tests/safety/ssrf-guardrails.test.ts && npm run typecheck`.
4. Confirm done condition: redirect paths cannot bypass SSRF guardrails and every hop is validated.
5. Do not mark task complete until the done condition is satisfied.
6. Write `.loop-commit-msg` with exactly one non-empty line: `04-02-task3`.
7. Update `.planning/STATE.md` with `phase=04-fetch-safety-and-compliance-guardrails` / `plan=04-02` / `task=3` / `status=implemented`.

## Section 43 — 04-fetch-safety-and-compliance-guardrails — 04-02 (Summary)
**Required inputs**
- Plan file: `.planning/phases/04-fetch-safety-and-compliance-guardrails/04-02-ssrf-network-guardrails-PLAN.md`
- Phase research: `.planning/phases/04-fetch-safety-and-compliance-guardrails/04-RESEARCH.md`

**Steps**
1. Create `.planning/phases/04-fetch-safety-and-compliance-guardrails/04-02-SUMMARY.md` by following `## Summary Creation Instructions` in this file.
2. Write `.loop-commit-msg` with exactly one non-empty line: `04-02-summary`.

## Section 44 — 04-fetch-safety-and-compliance-guardrails — 04-03 — Task 1 (Execution)
**Required inputs**
- Plan file: `.planning/phases/04-fetch-safety-and-compliance-guardrails/04-03-robots-compliance-fetch-wiring-PLAN.md`
- Phase research: `.planning/phases/04-fetch-safety-and-compliance-guardrails/04-RESEARCH.md`

**Steps**
1. Load `.planning/phases/04-fetch-safety-and-compliance-guardrails/04-RESEARCH.md` and use it as implementation reference.
2. Execute only Task 1 action: implement robots retrieval/evaluator returning explicit ALLOW/DENY/UNKNOWN/UNAVAILABLE outcomes with reason metadata.
3. Run verify checks one by one: `npm run test -- src/tests/fetch/fetch.safety-compliance.integration.test.ts`.
4. Confirm done condition: robots compliance stage exists as typed first-class decision engine.
5. Do not mark task complete until the done condition is satisfied.
6. Write `.loop-commit-msg` with exactly one non-empty line: `04-03-task1`.
7. Update `.planning/STATE.md` with `phase=04-fetch-safety-and-compliance-guardrails` / `plan=04-03` / `task=1` / `status=implemented`.

## Section 45 — 04-fetch-safety-and-compliance-guardrails — 04-03 — Task 2 (Execution)
**Required inputs**
- Plan file: `.planning/phases/04-fetch-safety-and-compliance-guardrails/04-03-robots-compliance-fetch-wiring-PLAN.md`
- Phase research: `.planning/phases/04-fetch-safety-and-compliance-guardrails/04-RESEARCH.md`

**Steps**
1. Load `.planning/phases/04-fetch-safety-and-compliance-guardrails/04-RESEARCH.md` and use it as implementation reference.
2. Execute only Task 2 action: wire staged pipeline safety preflight -> robots compliance -> HTTP retrieval and short-circuit on stage-specific denies.
3. Run verify checks one by one: `npm run test -- src/tests/fetch/fetch.safety-compliance.integration.test.ts`.
4. Confirm done condition: public `fetch(...)` exposes explicit safety/compliance outcomes and enforces preflight gating.
5. Do not mark task complete until the done condition is satisfied.
6. Write `.loop-commit-msg` with exactly one non-empty line: `04-03-task2`.
7. Update `.planning/STATE.md` with `phase=04-fetch-safety-and-compliance-guardrails` / `plan=04-03` / `task=2` / `status=implemented`.

## Section 46 — 04-fetch-safety-and-compliance-guardrails — 04-03 — Task 3 (Execution)
**Required inputs**
- Plan file: `.planning/phases/04-fetch-safety-and-compliance-guardrails/04-03-robots-compliance-fetch-wiring-PLAN.md`
- Phase research: `.planning/phases/04-fetch-safety-and-compliance-guardrails/04-RESEARCH.md`

**Steps**
1. Load `.planning/phases/04-fetch-safety-and-compliance-guardrails/04-RESEARCH.md` and use it as implementation reference.
2. Execute only Task 3 action: add end-to-end SAFE-01/SAFE-02 integration coverage including deny short-circuit before downstream fetch worker.
3. Run verify checks one by one: `npm run test -- src/tests/fetch/fetch.safety-compliance.integration.test.ts && npm run typecheck && npm run build`.
4. Confirm done condition: SAFE-01 and SAFE-02 are verified through typed fetch outcome tests.
5. Do not mark task complete until the done condition is satisfied.
6. Write `.loop-commit-msg` with exactly one non-empty line: `04-03-task3`.
7. Update `.planning/STATE.md` with `phase=04-fetch-safety-and-compliance-guardrails` / `plan=04-03` / `task=3` / `status=implemented`.

## Section 47 — 04-fetch-safety-and-compliance-guardrails — 04-03 (Summary)
**Required inputs**
- Plan file: `.planning/phases/04-fetch-safety-and-compliance-guardrails/04-03-robots-compliance-fetch-wiring-PLAN.md`
- Phase research: `.planning/phases/04-fetch-safety-and-compliance-guardrails/04-RESEARCH.md`

**Steps**
1. Create `.planning/phases/04-fetch-safety-and-compliance-guardrails/04-03-SUMMARY.md` by following `## Summary Creation Instructions` in this file.
2. Write `.loop-commit-msg` with exactly one non-empty line: `04-03-summary`.
3. Because this is the final plan in Phase 04, also update roadmap/state progress to reflect Phase 04 completion.

## Section 48 — 05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly — 05-01 — Task 1 (Execution)
**Required inputs**
- Plan file: `.planning/phases/05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly/05-01-frontend-dev-console-api-surface-PLAN.md`
- Phase research: `.planning/phases/05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly/05-RESEARCH.md`

**Steps**
1. Load `.planning/phases/05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly/05-RESEARCH.md` and use it as implementation reference.
2. Execute only Task 1 action: scaffold frontend server entrypoint/scripts, JSON handling, `/api/*` route mounting, and static serving while keeping SDK server-side.
3. Run verify checks one by one: `npm run typecheck` and start frontend dev script to verify `/api/search` and `/api/fetch`.
4. Confirm done condition: local frontend process exposes stable API entrypoints for both operations.
5. Do not mark task complete until the done condition is satisfied.
6. Write `.loop-commit-msg` with exactly one non-empty line: `05-01-task1`.
7. Update `.planning/STATE.md` with `phase=05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly` / `plan=05-01` / `task=1` / `status=implemented`.

## Section 49 — 05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly — 05-01 — Task 2 (Execution)
**Required inputs**
- Plan file: `.planning/phases/05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly/05-01-frontend-dev-console-api-surface-PLAN.md`
- Phase research: `.planning/phases/05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly/05-RESEARCH.md`

**Steps**
1. Load `.planning/phases/05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly/05-RESEARCH.md` and use it as implementation reference.
2. Execute only Task 2 action: implement zod API contracts + route handlers for `search`/`fetch` with duration tracking and typed safe envelopes.
3. Run verify checks one by one: `npm run typecheck` and manual `curl` checks for success + validation errors.
4. Confirm done condition: both primitives are callable over local API with deterministic inspectable envelopes.
5. Do not mark task complete until the done condition is satisfied.
6. Write `.loop-commit-msg` with exactly one non-empty line: `05-01-task2`.
7. Update `.planning/STATE.md` with `phase=05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly` / `plan=05-01` / `task=2` / `status=implemented`.

## Section 50 — 05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly — 05-01 — Task 3 (Execution)
**Required inputs**
- Plan file: `.planning/phases/05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly/05-01-frontend-dev-console-api-surface-PLAN.md`
- Phase research: `.planning/phases/05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly/05-RESEARCH.md`

**Steps**
1. Load `.planning/phases/05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly/05-RESEARCH.md` and use it as implementation reference.
2. Execute only Task 3 action: add route-level tests for request validation, typed failures, and safety/compliance error visibility.
3. Run verify checks one by one: `npm run test -- src/tests/frontend-api/routes.contracts.test.ts`.
4. Confirm done condition: API behavior for both operations is validated by executable tests.
5. Do not mark task complete until the done condition is satisfied.
6. Write `.loop-commit-msg` with exactly one non-empty line: `05-01-task3`.
7. Update `.planning/STATE.md` with `phase=05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly` / `plan=05-01` / `task=3` / `status=implemented`.

## Section 51 — 05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly — 05-01 (Summary)
**Required inputs**
- Plan file: `.planning/phases/05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly/05-01-frontend-dev-console-api-surface-PLAN.md`
- Phase research: `.planning/phases/05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly/05-RESEARCH.md`

**Steps**
1. Create `.planning/phases/05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly/05-01-SUMMARY.md` by following `## Summary Creation Instructions` in this file.
2. Write `.loop-commit-msg` with exactly one non-empty line: `05-01-summary`.

## Section 52 — 05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly — 05-02 — Task 1 (Execution)
**Required inputs**
- Plan file: `.planning/phases/05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly/05-02-frontend-ui-invocation-and-output-PLAN.md`
- Phase research: `.planning/phases/05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly/05-RESEARCH.md`

**Steps**
1. Load `.planning/phases/05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly/05-RESEARCH.md` and use it as implementation reference.
2. Execute only Task 1 action: build dual-panel UI layout for independent search/fetch invocation and visible status/duration/timestamp output zones.
3. Run verify checks one by one: manual frontend run to confirm both panels render with distinct controls/outputs.
4. Confirm done condition: UI supports independent invocation and output inspection for both operations.
5. Do not mark task complete until the done condition is satisfied.
6. Write `.loop-commit-msg` with exactly one non-empty line: `05-02-task1`.
7. Update `.planning/STATE.md` with `phase=05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly` / `plan=05-02` / `task=1` / `status=implemented`.

## Section 53 — 05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly — 05-02 — Task 2 (Execution)
**Required inputs**
- Plan file: `.planning/phases/05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly/05-02-frontend-ui-invocation-and-output-PLAN.md`
- Phase research: `.planning/phases/05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly/05-RESEARCH.md`

**Steps**
1. Load `.planning/phases/05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly/05-RESEARCH.md` and use it as implementation reference.
2. Execute only Task 2 action: wire client submit handlers and explicit per-operation state machine (`idle/running/success/error`) for `/api/search` and `/api/fetch`.
3. Run verify checks one by one: manual browser run confirms each button triggers matching API and updates state/output correctly.
4. Confirm done condition: both operations are invokable from UI with clear state/result visibility.
5. Do not mark task complete until the done condition is satisfied.
6. Write `.loop-commit-msg` with exactly one non-empty line: `05-02-task2`.
7. Update `.planning/STATE.md` with `phase=05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly` / `plan=05-02` / `task=2` / `status=implemented`.

## Section 54 — 05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly — 05-02 — Task 3 (Execution)
**Required inputs**
- Plan file: `.planning/phases/05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly/05-02-frontend-ui-invocation-and-output-PLAN.md`
- Phase research: `.planning/phases/05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly/05-RESEARCH.md`

**Steps**
1. Load `.planning/phases/05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly/05-RESEARCH.md` and use it as implementation reference.
2. Execute only Task 3 action: harden rendering for debugging (pretty JSON, metadata separation, typed error blocks).
3. Run verify checks one by one: manual success/failure tests confirm readable complete outputs without ambiguity.
4. Confirm done condition: users can quickly understand request, response, and failure reason.
5. Do not mark task complete until the done condition is satisfied.
6. Write `.loop-commit-msg` with exactly one non-empty line: `05-02-task3`.
7. Update `.planning/STATE.md` with `phase=05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly` / `plan=05-02` / `task=3` / `status=implemented`.

## Section 55 — 05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly — 05-02 (Summary)
**Required inputs**
- Plan file: `.planning/phases/05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly/05-02-frontend-ui-invocation-and-output-PLAN.md`
- Phase research: `.planning/phases/05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly/05-RESEARCH.md`

**Steps**
1. Create `.planning/phases/05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly/05-02-SUMMARY.md` by following `## Summary Creation Instructions` in this file.
2. Write `.loop-commit-msg` with exactly one non-empty line: `05-02-summary`.

## Section 56 — 05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly — 05-03 — Task 1 (Execution)
**Required inputs**
- Plan file: `.planning/phases/05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly/05-03-run-both-history-and-phase-verification-PLAN.md`
- Phase research: `.planning/phases/05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly/05-RESEARCH.md`

**Steps**
1. Load `.planning/phases/05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly/05-RESEARCH.md` and use it as implementation reference.
2. Execute only Task 1 action: add deterministic `Run Both` orchestration (search then fetch) with separate visible outputs and non-crashing no-URL warning.
3. Run verify checks one by one: manual browser test confirms single action triggers both operations and keeps outputs distinct.
4. Confirm done condition: single-action flow exists while preserving operation-specific output clarity.
5. Do not mark task complete until the done condition is satisfied.
6. Write `.loop-commit-msg` with exactly one non-empty line: `05-03-task1`.
7. Update `.planning/STATE.md` with `phase=05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly` / `plan=05-03` / `task=1` / `status=implemented`.

## Section 57 — 05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly — 05-03 — Task 2 (Execution)
**Required inputs**
- Plan file: `.planning/phases/05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly/05-03-run-both-history-and-phase-verification-PLAN.md`
- Phase research: `.planning/phases/05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly/05-RESEARCH.md`

**Steps**
1. Load `.planning/phases/05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly/05-RESEARCH.md` and use it as implementation reference.
2. Execute only Task 2 action: implement bounded in-memory call history and replay controls for search/fetch without disk persistence.
3. Run verify checks one by one: manual verification of history entries and successful replay for at least one search and one fetch.
4. Confirm done condition: users can compare and rerun recent calls without retyping payloads.
5. Do not mark task complete until the done condition is satisfied.
6. Write `.loop-commit-msg` with exactly one non-empty line: `05-03-task2`.
7. Update `.planning/STATE.md` with `phase=05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly` / `plan=05-03` / `task=2` / `status=implemented`.

## Section 58 — 05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly — 05-03 — Task 3 (Execution)
**Required inputs**
- Plan file: `.planning/phases/05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly/05-03-run-both-history-and-phase-verification-PLAN.md`
- Phase research: `.planning/phases/05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly/05-RESEARCH.md`

**Steps**
1. Load `.planning/phases/05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly/05-RESEARCH.md` and use it as implementation reference.
2. Execute only Task 3 action: extend route tests and add frontend smoke test for invocation/output flow with deterministic CI behavior.
3. Run verify checks one by one: `npm run test -- src/tests/frontend-api/routes.contracts.test.ts src/tests/frontend-ui/dev-console.smoke.test.ts`, then `npm run typecheck && npm run build`.
4. Confirm done condition: Phase 05 behavior is protected by executable verification for visible invocation/output requirements.
5. Do not mark task complete until the done condition is satisfied.
6. Write `.loop-commit-msg` with exactly one non-empty line: `05-03-task3`.
7. Update `.planning/STATE.md` with `phase=05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly` / `plan=05-03` / `task=3` / `status=implemented`.

## Section 59 — 05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly — 05-03 (Summary)
**Required inputs**
- Plan file: `.planning/phases/05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly/05-03-run-both-history-and-phase-verification-PLAN.md`
- Phase research: `.planning/phases/05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly/05-RESEARCH.md`

**Steps**
1. Create `.planning/phases/05-add-a-frontend-where-i-can-display-if-these-functions-work-i-want-to-see-both-functions-being-called-and-the-output-clearly/05-03-SUMMARY.md` by following `## Summary Creation Instructions` in this file.
2. Write `.loop-commit-msg` with exactly one non-empty line: `05-03-summary`.
3. Because this is the final plan in Phase 05, also update roadmap/state progress to reflect Phase 05 completion.
