# Session-Aware Web Crawl Design

## Goal

Upgrade `web_crawl` from a plain HTTP page fetch into a first-class session-aware crawl pipeline that can recover evidence from public pages, rendered pages, and authenticated pages backed by stored session state.

The agent must keep a single crawl tool surface:

- `web_crawl(url, objective)`

The crawler must internally resolve the right fetch strategy, auto-match a stored session profile by domain, escalate from HTTP to browser when needed, and return typed success only when useful evidence was actually recovered.

## Non-Goals

- CAPTCHA solving
- Anti-bot evasion systems
- Freeform login automation driven by prompts
- Prompt-supplied raw credentials or secrets
- Full site-specific custom adapters in v1

## Current Problem

The current crawler is centered on `HttpFetchWorker`, which performs a single HTTP fetch and then extracts content. This fails on sites that:

- require a recognizable request identity
- rely on JavaScript rendering
- require authenticated session state
- return bot, auth, or interstitial pages instead of article content

Today, the runtime can still produce a completed answer even when crawl evidence is empty. That makes failures hard to see and encourages unsupported no-evidence answers.

## Recommended Approach

Keep `web_crawl` as the only agent-facing crawl tool, but make it an orchestrated multi-strategy fetch pipeline with browser fallback as a first-class path.

The recommended execution order is:

1. Validate URL and retrieval-policy scope.
2. Resolve a stored session profile by domain.
3. Run HTTP fetch unless the matched profile forces browser mode.
4. Classify the HTTP result.
5. Escalate to browser when HTTP is blocked, challenge-like, auth-gated, JS-only, or too thin to extract useful content.
6. Seed browser state from the matched session profile.
7. Navigate, capture rendered content, normalize it, and extract evidence.
8. Return typed success only if evidence is recovered.
9. Otherwise return a typed error with an explicit classification.

## Architecture

The crawler stays split into small task-focused modules:

- `backend/app/crawler/session_profiles.py`
  - Load and resolve domain-matched session profiles.
- `backend/app/crawler/fetch_strategy.py`
  - Decide whether to start with HTTP or browser and whether to escalate.
- `backend/app/crawler/fetch_orchestrator.py`
  - Coordinate the full crawl sequence.
- `backend/app/crawler/browser_worker.py`
  - Run Playwright-backed navigation and rendered content capture.
- `backend/app/crawler/fetch_classification.py`
  - Classify outcomes like blocked, auth required, challenge detected, or low-content-quality.
- `backend/app/crawler/content_normalizer.py`
  - Normalize HTTP or browser output into common extraction input.
- `backend/app/crawler/error_mapping.py`
  - Convert internal failures into stable typed crawl errors.

Existing modules remain focused:

- `http_worker.py` handles cheap HTTP fetches.
- `extractor.py` handles evidence extraction from normalized content.
- `web_crawl.py` remains the tool boundary and contract owner.

## Session Profiles

Session profiles are backend-managed configuration records, not prompt inputs.

They are auto-matched by domain when `web_crawl` is called. For example:

- `domains=["wikipedia.org"]`
- `domains=["app.example.com", "dashboard.example.com"]`

Each profile may include:

- profile id
- domain match rules
- cookies
- custom headers
- local storage seed values
- session storage seed values
- browser-only flag
- TTL or freshness metadata

The crawler never asks the agent to supply raw secret values. The agent only requests the crawl target and objective.

## Schema Plan

Add focused Pydantic models under crawler-local `schemas/`:

- `backend/app/crawler/schemas/session_profile.py`
  - `SessionProfile`
  - `SessionCookie`
  - `SessionHeader`
  - `StorageSeedEntry`
  - `DomainSessionMatch`
- `backend/app/crawler/schemas/browser_fetch.py`
  - `BrowserFetchSuccess`
  - `BrowserFetchFailure`
  - `BrowserContextSeed`
- `backend/app/crawler/schemas/fetch_strategy.py`
  - `FetchStrategyDecision`
  - `FetchEscalationReason`
  - `FetchClassification`

Extend crawl success metadata so typed results can surface:

- `strategy_used`
- `escalation_count`
- `session_profile_id`
- `block_reason`
- `rendered`
- `challenge_detected`

## Fetch Strategy

The strategy decision should be deterministic code, not LLM behavior.

Default behavior:

- try HTTP first
- classify the result
- escalate to browser if:
  - status is `401` or `403`
  - content is a login gate or challenge page
  - extracted content is too thin
  - the page appears to require client-side rendering
  - the matched session profile requires browser mode

This gives the crawler a cheap path for simple pages and a first-class rendered path for harder sites.

## Browser Fetch

Browser fetch should be built on Playwright and run entirely in code.

It must:

1. create a browser context
2. inject matched session profile state before navigation
   - cookies
   - local storage
   - session storage
   - optional extra headers
3. navigate to the target URL with bounded wait rules
4. capture final URL, rendered HTML, and visible text
5. hand normalized content to the existing extraction pipeline

The browser worker should support deterministic, profile-configured bootstrap only. It should not execute arbitrary login macros in v1.

## Execution Flow

End-to-end `web_crawl` flow:

1. `web_crawl` receives `url` and `objective`.
2. Domain scope validation runs first.
3. Session profile resolver finds a matching profile or returns no match.
4. Fetch strategy decides initial mode.
5. HTTP worker or browser worker executes.
6. Result classifier labels the outcome.
7. If escalation is required, browser fetch runs with injected profile state.
8. Content normalizer produces extraction input.
9. Extractor produces typed excerpts and markdown/text output.
10. Tool returns:
   - success if evidence exists
   - typed failure if evidence does not exist or access was blocked

## Error Handling

The crawler should return explicit typed categories instead of hiding failures behind empty answers.

Target classifications:

- `blocked`
- `auth_required`
- `challenge_detected`
- `low_content_quality`
- `browser_navigation_failed`
- `session_profile_misconfigured`
- `unsupported_content_type`
- `network_error`

Important behavioral change:

- if crawl-backed retrieval ends with zero evidence after strategy attempts, that should not be treated as a successful evidence-bearing crawl

## Logging

Observability must be upgraded at the runtime and tool boundaries.

For each `web_crawl` run, logs should include:

- URL
- matched session profile id
- chosen strategy
- escalation reason
- final URL
- status code
- classification
- evidence count
- extracted text length
- fallback reason

For run-level summaries, logs should warn when the agent completes after tool use with zero sources.

## Testing Plan

Add focused tests for:

- domain-to-session-profile auto-matching
- HTTP-first strategy selection
- forced-browser session profiles
- HTTP to browser escalation on `401` and `403`
- escalation on low-content extraction
- browser bootstrap for cookies, headers, local storage, and session storage
- typed result metadata fields
- typed failure categories
- regression for the Wikipedia case:
  - HTTP path blocked
  - escalation reason logged
  - browser/session-aware path attempted
  - final outcome clearly typed

## Rollout Plan

Phase the work to keep risk controlled:

1. Introduce session profile schemas and resolver.
2. Add fetch strategy and orchestration modules.
3. Implement browser worker with seeded session state.
4. Extend crawl result metadata and error classifications.
5. Update `web_crawl` to use the orchestrator.
6. Tighten runtime behavior around zero-evidence completions.
7. Add regression tests and targeted logs.

## Open Questions

These are intentionally deferred from v1:

- where session profiles are stored and edited
- how profile secrets are loaded at runtime
- whether a later phase should support scripted authenticated bootstrap flows
- whether some domains should skip HTTP entirely based on historical failures
