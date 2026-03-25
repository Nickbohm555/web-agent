---
phase: 3
slug: deep-agents-persistence-backbone
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-24
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `pytest 7.1.2` for backend, `vitest 4.1.0` for frontend/server contracts |
| **Config file** | `none` |
| **Quick run command** | `pytest backend/tests/agent/test_deep_research_runtime.py backend/tests/api/test_agent_run_service.py -q` |
| **Full suite command** | `pytest backend/tests -q && npm test` |
| **Estimated runtime** | ~180 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest backend/tests/agent/test_deep_research_runtime.py backend/tests/api/test_agent_run_service.py -q`
- **After every plan wave:** Run `pytest backend/tests -q`
- **Before `$gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 180 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | PLAN-03 | unit/integration | `pytest backend/tests/agent/test_deep_agent_persistence.py -q` | ❌ W0 | ⬜ pending |
| 03-01-02 | 01 | 1 | PLAN-01 | unit/integration | `pytest backend/tests/agent/test_deep_agent_persistence.py -q` | ❌ W0 | ⬜ pending |
| 03-01-03 | 01 | 1 | PLAN-02 | unit/integration | `pytest backend/tests/agent/test_deep_agent_persistence.py -q` | ❌ W0 | ⬜ pending |
| 03-02-01 | 02 | 2 | PLAN-01 | integration | `pytest backend/tests/agent/test_deep_research_runtime.py -q` | ✅ | ⬜ pending |
| 03-02-02 | 02 | 2 | PLAN-03 | integration | `pytest backend/tests/agent/test_deep_agent_resume.py -q` | ❌ W0 | ⬜ pending |
| 03-02-03 | 02 | 2 | PLAN-04 | integration/contract | `pytest backend/tests/agent/test_deep_agent_logging.py -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/agent/test_deep_agent_persistence.py` — durable plan artifact creation and namespace routing
- [ ] `backend/tests/agent/test_deep_agent_resume.py` — checkpoint resume with stable `thread_id`
- [ ] `backend/tests/agent/test_deep_agent_logging.py` — structured progress logging and status artifact updates
- [ ] `backend/tests/conftest.py` or a dedicated helper — Postgres-backed test fixture for saver/store integration
- [ ] Docker or test env support for Postgres if the phase uses a compose-managed local database

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Inspect persisted artifacts outside the frontend in-memory history store | PLAN-04 | Requires checking real stored files and logs after an interrupted and resumed run | Start a deep research run, inspect `/runs/{run_id}/plan.md` and `/runs/{run_id}/status.json`, restart the backend path, resume with the same `thread_id`, and confirm status/log continuity |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all missing references
- [ ] No watch-mode flags
- [ ] Feedback latency < 180s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
