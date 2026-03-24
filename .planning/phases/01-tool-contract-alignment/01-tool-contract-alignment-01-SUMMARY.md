---
phase: 01-tool-contract-alignment
plan: "01"
subsystem: api
tags: [langchain, runtime, tools, retrieval, open_url]
requires: []
provides:
  - Canonical backend runtime bindings expose web_search and open_url across quick, agentic, and deep-research profiles.
  - Backend source extraction accepts both open_url and legacy web_crawl tool messages.
  - Backend regression tests lock prompt guidance, parser tolerance, and open_page action semantics to the renamed contract.
affects: [frontend, telemetry, deep_research, testing]
tech-stack:
  added: []
  patterns:
    - Explicit canonical tool naming with compatibility aliases for behavior-preserving contract renames.
    - Parser boundaries accept mixed-version tool events while runtime emitters use the new canonical tool name.
key-files:
  created:
    - .planning/phases/01-tool-contract-alignment/01-tool-contract-alignment-01-SUMMARY.md
  modified:
    - backend/agent/prompts.py
    - backend/agent/runtime_constants.py
    - backend/agent/runtime_execution.py
    - backend/agent/runtime_sources.py
    - backend/app/tools/__init__.py
    - backend/app/tools/web_crawl.py
    - backend/tests/agent/test_runtime.py
    - backend/tests/tools/test_web_crawl_tool.py
key-decisions:
  - Keep run_web_crawl and WebCrawl schemas unchanged while exposing open_url as the user-facing LangChain tool.
  - Preserve web_crawl as an import-stability alias and accept both names in runtime source parsing.
patterns-established:
  - Canonical tool names live in runtime constants and are asserted at runtime.
  - Retrieval action records stay on open_page/open_page_batch even when the tool name changes.
requirements-completed: [TOOL-01, TOOL-02]
duration: 25min
completed: 2026-03-24
---

# Phase 01: Tool Contract Alignment Summary

**Backend runtime bindings now expose `open_url` canonically while preserving crawl behavior and mixed-version source parsing**

## Performance

- **Duration:** 25 min
- **Started:** 2026-03-24T02:00:00-04:00
- **Completed:** 2026-03-24T02:12:00-04:00
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments
- Renamed the backend page-opening contract from `web_crawl` to `open_url` across runtime constants, prompt guidance, and tool exports.
- Kept `run_web_crawl(...)` behavior intact while exposing `open_url` as the canonical LangChain tool and preserving a `web_crawl` alias.
- Added regression coverage proving backend parsers accept both `open_url` and legacy `web_crawl` while action records remain `open_page`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Rename the canonical backend page-opening tool contract to open_url** - `9c00ccc` (feat)
2. **Task 2: Make backend source extraction tolerate both tool names and lock it with regression tests** - `b26f3c2` (test)

## Files Created/Modified
- `backend/agent/runtime_constants.py` - Canonical runtime tool names now assert `web_search` plus `open_url`.
- `backend/agent/runtime_execution.py` - Runtime tool construction now returns the canonical `open_url` tool object.
- `backend/agent/prompts.py` - Agent guidance now instructs `open_url` usage everywhere.
- `backend/agent/runtime_sources.py` - Source extraction accepts both `open_url` and legacy `web_crawl` tool messages.
- `backend/app/tools/web_crawl.py` - Canonical LangChain tool name is `open_url` with a compatibility alias for `web_crawl`.
- `backend/app/tools/__init__.py` - Package exports now resolve `open_url` explicitly.
- `backend/tests/agent/test_runtime.py` - Runtime and parser regression coverage tracks the renamed contract.
- `backend/tests/tools/test_web_crawl_tool.py` - Tool-level tests lock the canonical name and `open_page` action semantics.

## Decisions Made
- Used a compatibility alias instead of renaming crawl internals to keep this phase contract-only.
- Made parser tolerance explicit in `runtime_sources.py` so mixed-version history and tool payloads remain readable.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Extended parser tolerance during Task 1 to keep the backend suite green**
- **Found during:** Task 1 (Rename the canonical backend page-opening tool contract to open_url)
- **Issue:** Renaming the canonical tool immediately broke source extraction because the parser only recognized `web_crawl`.
- **Fix:** Added explicit dual-name crawl parsing in `backend/agent/runtime_sources.py` before finishing the rename.
- **Files modified:** `backend/agent/runtime_sources.py`
- **Verification:** `python -m pytest backend/tests/agent/test_runtime.py backend/tests/tools/test_web_crawl_tool.py -q`
- **Committed in:** `9c00ccc`

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** The deviation was necessary to preserve runtime correctness under the renamed contract. No scope creep beyond planned parser tolerance.

## Issues Encountered
- None beyond the expected parser-tolerance blocker addressed during Task 1.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Frontend contract and telemetry surfaces can now align to `open_url` against a stable backend contract.
- Phase 1 backend validation is green on the targeted pytest suite.

---
*Phase: 01-tool-contract-alignment*
*Completed: 2026-03-24*
