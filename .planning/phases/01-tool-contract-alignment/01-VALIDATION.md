---
phase: 01
slug: tool-contract-alignment
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-03-24
---

# Phase 01 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `pytest` + `vitest@4.1.0` |
| **Config file** | `package.json` for Vitest; pytest uses repo defaults in `backend/tests/` |
| **Quick run command** | `python -m pytest backend/tests/agent/test_runtime.py backend/tests/tools/test_web_crawl_tool.py -q` |
| **Full suite command** | `python -m pytest backend/tests -q && npm test -- --runInBand` |
| **Estimated runtime** | ~120 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest backend/tests/agent/test_runtime.py backend/tests/tools/test_web_crawl_tool.py -q`
- **After every plan wave:** Run `npm test -- src/tests/frontend-api/run-events.contracts.test.ts src/tests/frontend-api/observability-correlation.test.ts src/tests/frontend-api/run-history.integration.test.ts src/tests/frontend-api/runs.stream.test.ts src/tests/frontend/state.test.ts src/tests/frontend/timeline.test.ts`
- **Before `$gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 120 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 1 | TOOL-01 | unit/integration | `python -m pytest backend/tests/agent/test_runtime.py -q` | ✅ | ⬜ pending |
| 01-02-01 | 02 | 1 | TOOL-02 | unit/integration | `python -m pytest backend/tests/agent/test_runtime.py backend/tests/tools/test_web_crawl_tool.py -q` | ✅ | ⬜ pending |
| 01-03-01 | 03 | 2 | TOOL-01, TOOL-02 | contract/integration | `npm test -- src/tests/frontend-api/run-events.contracts.test.ts src/tests/frontend-api/observability-correlation.test.ts src/tests/frontend-api/run-history.integration.test.ts src/tests/frontend-api/runs.stream.test.ts src/tests/frontend/state.test.ts src/tests/frontend/timeline.test.ts` | ✅ | ⬜ pending |
| 01-03-02 | 03 | 2 | TOOL-01, TOOL-02 | phase gate | `python -m pytest backend/tests -q && npm test -- --runInBand` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/agent/test_runtime.py` — assert canonical tool names are `("web_search", "open_url")`
- [ ] `backend/tests/tools/test_web_crawl_tool.py` or nearby runtime-source tests — prove parser compatibility for `open_url` and any retained legacy `web_crawl`
- [ ] `src/tests/frontend-api/run-events.contracts.test.ts` — validate `tool_name: "open_url"` contract parsing
- [ ] `src/tests/frontend-api/observability-correlation.test.ts` or `src/tests/frontend-api/run-history.integration.test.ts` — prove `open_url` still maps to retrieval action `open_page`

*If none: "Existing infrastructure covers all phase requirements."*

---

## Manual-Only Verifications

All phase behaviors have automated verification.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
