---
phase: 4
slug: deep-agents-research-fan-out
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-24
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `pytest 7.1.2` |
| **Config file** | none — pytest autodiscovery |
| **Quick run command** | `pytest backend/tests/agent/test_deep_research_subagents.py -q` |
| **Full suite command** | `pytest backend/tests -q` |
| **Estimated runtime** | ~90 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest backend/tests/agent/test_deep_research_subagents.py -q`
- **After every plan wave:** Run `pytest backend/tests/agent/test_deep_research_runtime.py -q`
- **Before `$gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 90 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 4-01-01 | 01 | 0 | RSCH-01 | unit | `pytest backend/tests/agent/test_deep_research_subagents.py -q -k fanout` | ❌ W0 | ⬜ pending |
| 4-01-02 | 01 | 0 | RSCH-02 | unit | `pytest backend/tests/agent/test_deep_research_subagents.py -q -k retrieval` | ❌ W0 | ⬜ pending |
| 4-02-01 | 02 | 1 | RSCH-01 | integration | `pytest backend/tests/agent/test_deep_research_runtime.py -q -k progress` | ✅ | ⬜ pending |
| 4-02-02 | 02 | 1 | RSCH-02 | integration | `pytest backend/tests/agent/test_deep_research_runtime.py -q -k evidence` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/agent/test_deep_research_subagents.py` — add fan-out, retrieval reuse, and artifact/progress coverage for RSCH-01 and RSCH-02
- [ ] `backend/tests/agent/test_deep_research_runtime.py` — extend runtime coverage for fan-out stage transitions and artifact persistence
- [ ] Deep Agents dependency smoke check — add a focused import/config test that fails clearly when `deepagents` or compatible package versions are missing

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Parallel subquestion progress is inspectable in persisted artifacts or logs during a live run | RSCH-01 | Unit tests can validate saved records, but they do not prove operator-visible progress during a running background job | Start one `deep_research` run with at least two derived subquestions, inspect persisted phase artifacts or runtime logs while the run is active, and confirm each subquestion shows pending then completed or failed status updates |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 90s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
