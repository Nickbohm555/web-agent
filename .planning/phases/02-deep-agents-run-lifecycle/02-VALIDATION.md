---
phase: 2
slug: deep-agents-run-lifecycle
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-24
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `pytest` |
| **Config file** | `none` |
| **Quick run command** | `pytest backend/tests/agent/test_deep_research_runtime.py backend/tests/api/test_agent_run_service.py -q` |
| **Full suite command** | `pytest backend/tests/agent/test_deep_research_runtime.py backend/tests/agent/test_runtime.py backend/tests/api/test_agent_run_service.py backend/tests/api/test_agent_run_route.py -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest backend/tests/agent/test_deep_research_runtime.py backend/tests/api/test_agent_run_service.py -q`
- **After every plan wave:** Run `pytest backend/tests/agent/test_deep_research_runtime.py backend/tests/agent/test_runtime.py backend/tests/api/test_agent_run_service.py backend/tests/api/test_agent_run_route.py -q`
- **Before `$gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | DEEP-01 | unit | `pytest backend/tests/agent/test_deep_research_runtime.py -q` | ✅ | ⬜ pending |
| 02-01-02 | 01 | 1 | DEEP-01 | integration | `pytest backend/tests/api/test_agent_run_service.py backend/tests/api/test_agent_run_route.py -q` | ✅ | ⬜ pending |
| 02-02-01 | 02 | 2 | DEEP-02 | unit | `pytest backend/tests/agent/test_deep_research_runtime.py -q` | ✅ | ⬜ pending |
| 02-02-02 | 02 | 2 | DEEP-03 | integration | `pytest backend/tests/api/test_agent_run_service.py backend/tests/api/test_agent_run_route.py backend/tests/agent/test_runtime.py -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/agent/test_deep_research_runtime.py` — expand lifecycle tests for Deep Agents start, pause, and resume
- [ ] `backend/tests/api/test_agent_run_service.py` — cover the service-layer deep-research start/resume contract
- [ ] `backend/tests/api/test_agent_run_route.py` — confirm HTTP response shape remains valid for queued or clarification-pending deep-research responses

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Compatible `deepagents` package selection against pinned LangChain packages | DEEP-01 | Package resolution may require environment-specific validation beyond current unit tests | Install backend requirements plus `deepagents`, import the Deep Agents factory, and confirm the backend app boots without import or dependency conflicts |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
