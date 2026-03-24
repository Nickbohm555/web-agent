---
phase: 5
slug: evidence-grounded-completion
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-24
---

# Phase 5 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `backend/pyproject.toml` |
| **Quick run command** | `pytest backend/tests/agent/test_deep_research_runtime.py` |
| **Full suite command** | `pytest backend/tests/agent backend/tests/api` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest backend/tests/agent/test_deep_research_runtime.py`
- **After every plan wave:** Run `pytest backend/tests/agent backend/tests/api`
- **Before `$gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 5-01-01 | 01 | 1 | RSCH-03 | unit | `pytest backend/tests/agent/test_deep_research_runtime.py -k subagent_contract` | ✅ | ⬜ pending |
| 5-01-02 | 01 | 1 | RSCH-03 | unit | `pytest backend/tests/agent/test_deep_research_runtime.py -k middleware` | ✅ | ⬜ pending |
| 5-02-01 | 02 | 2 | RSCH-04, DEEP-04 | unit | `pytest backend/tests/agent/test_deep_research_runtime.py -k sufficiency` | ✅ | ⬜ pending |
| 5-02-02 | 02 | 2 | TOOL-03 | integration | `pytest backend/tests/agent/test_deep_research_runtime.py -k final_answer` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/agent/test_deep_research_runtime.py` - extend fixtures for typed subagent results and repeated research passes
- [ ] `backend/tests/agent/test_runtime.py` - add response-envelope assertions for deep research completion

---

## Manual-Only Verifications

All phase behaviors have automated verification.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
