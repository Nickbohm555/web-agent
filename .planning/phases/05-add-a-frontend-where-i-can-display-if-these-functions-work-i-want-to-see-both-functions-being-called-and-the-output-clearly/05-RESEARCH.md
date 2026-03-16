# Phase 05: Add a frontend where I can display if these functions work. I want to see both functions being called and the output clearly - Research

**Researched:** 2026-03-15  
**Domain:** Local frontend validation surface for SDK `search(...)` and `fetch(...)`  
**Confidence:** HIGH

## Summary

Phase 05 should prioritize a **local developer console UI** that is intentionally simple, stable, and directly useful for debugging the SDK primitives. The fastest, lowest-overhead path for this repo is a single Node process that serves a static frontend and exposes thin local API routes that call the SDK methods (`search` and `fetch`) and return normalized JSON.

Given current project scope (SDK-first, no packaging yet, Phase 4 dependency), the frontend should optimize for transparency over polish: show exact request payloads, call timing, success/error status, and full response bodies for both operations. This phase is not about production UX; it is about fast validation loops and clear failure diagnostics (rate limits, URL validation failures, safety/robots denies, and timeouts).

A second option (Vite-based SPA) is valid if rapid UI iteration becomes painful with no-build static assets, but it should be treated as optional complexity. The core recommendation is to start with Express + static HTML/JS + explicit `/api/search` and `/api/fetch` endpoints.

**Primary recommendation:** Implement a single-process local dev console: `express.static` UI + validated JSON API routes that call SDK primitives and render request/response/timing/error details side-by-side.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `express` | `5.2.1` | Local API endpoints + static file serving | Already installed; built-in `express.json` and `express.static` cover this phase cleanly |
| `zod` | `4.3.6` | Validate and normalize inbound UI payloads before SDK calls | Prevents malformed requests and makes error messages deterministic |
| `typescript` | `5.9.3` | Shared contracts for route input/output and UI payload shapes | Keeps API/UI contract drift low during rapid iteration |
| `vitest` | `4.1.0` | Route-level and utility-level tests | Already in stack; fast feedback for request validation and error mapping |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `vite` | `latest` (optional) | Faster UI iteration with HMR and proxy support | Use only if static frontend editing becomes a bottleneck |
| `@playwright/test` | `latest` (optional) | End-to-end verification of manual flow | Add when you need reliable regression checks for UI + API wiring |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Express static + API in one process | Vite frontend + separate API server | Better DX/HMR but adds dev server orchestration and proxy config |
| Vanilla JS view layer | React + Vite | Better component scaling but adds framework/runtime overhead for a debug console |
| Plain `<pre>` JSON output | JSON viewer component | Better UX for nested payloads, but unnecessary dependency for initial phase |

**Installation (primary path):**
```bash
# no new runtime deps required for primary architecture
npm install
```

**Installation (optional enhancement path):**
```bash
npm install -D vite @playwright/test
```

## Architecture Patterns

### Recommended Project Structure
```
src/
├── sdk/                    # public search/fetch methods
├── frontend/
│   ├── server.ts           # express app boot + route wiring
│   ├── routes/
│   │   ├── search.ts       # POST /api/search
│   │   └── fetch.ts        # POST /api/fetch
│   └── contracts.ts        # zod schemas for request/response envelopes
├── tests/
│   ├── frontend-api/       # vitest route/contract tests
│   └── e2e/                # optional playwright tests
└── public/
    ├── index.html          # dev console UI
    ├── app.js              # UI state/event handling
    └── styles.css          # lightweight layout styles
```

### Pattern 1: Thin API Route, Thick SDK Call Result Envelope
**What:** Keep route handlers minimal: validate input, call SDK, return a consistent envelope with timing and structured error details.  
**When to use:** Every frontend-invoked route (`/api/search`, `/api/fetch`).  
**Example:**
```typescript
// Source: https://expressjs.com/en/api.html#express.json and https://zod.dev/
const SearchRequest = z.object({
  query: z.string().min(1),
  options: z.object({ maxResults: z.number().int().positive().max(20).optional() }).default({}),
});

app.post("/api/search", async (req, res) => {
  const startedAt = Date.now();
  const parsed = SearchRequest.safeParse(req.body);
  if (!parsed.success) return res.status(400).json({ ok: false, error: { code: "VALIDATION_ERROR", details: parsed.error.flatten() } });

  try {
    const data = await sdk.search(parsed.data.query, parsed.data.options);
    return res.json({ ok: true, operation: "search", durationMs: Date.now() - startedAt, request: parsed.data, data });
  } catch (err) {
    return res.status(500).json({ ok: false, operation: "search", durationMs: Date.now() - startedAt, error: normalizeError(err) });
  }
});
```

### Pattern 2: Explicit UI Request State Machine
**What:** Model each operation with explicit states (`idle` -> `running` -> `success|error`) and render each state directly.  
**When to use:** Search and fetch panels independently, plus a combined "run both" flow.  
**Example:**
```typescript
// Source: https://developer.mozilla.org/en-US/docs/Web/API/AbortController
type CallState = "idle" | "running" | "success" | "error";

async function invoke(endpoint: "/api/search" | "/api/fetch", payload: unknown) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  setState({ status: "running", request: payload });
  try {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
    const json = await response.json();
    setState({ status: response.ok ? "success" : "error", response: json });
  } catch (error) {
    setState({ status: "error", response: { ok: false, error: { code: "NETWORK_OR_TIMEOUT", message: String(error) } } });
  } finally {
    clearTimeout(timeout);
  }
}
```

### Pattern 3: Local Frontend Serving with Explicit API Prefix
**What:** Serve static assets and API routes from the same Express app, with `/api/*` namespace to avoid route collision.  
**When to use:** Primary architecture option for this phase.  
**Example:**
```typescript
// Sources: https://expressjs.com/en/starter/static-files.html
app.use(express.json({ limit: "100kb" }));
app.use("/api", apiRouter);
app.use(express.static("public"));
app.get("*", (_req, res) => res.sendFile(path.join(process.cwd(), "public/index.html")));
```

### Anti-Patterns to Avoid
- **Direct SDK calls from browser:** exposes secrets and bypasses server-side safety controls.
- **Unvalidated request bodies:** produces noisy runtime errors and unclear UX.
- **Single shared output pane without call history:** loses debuggability across retries/variants.
- **Silent failures:** always show status, error code, message, and (safe) details.
- **"Pretty only" output:** must include raw JSON and timing metadata, not just formatted snippets.

## UX Flow and Component Guidance

### Recommended UX Flow
1. User opens local dev console.
2. User fills **Search form** (`query`, options) and/or **Fetch form** (`url`, options).
3. User clicks `Run Search`, `Run Fetch`, or `Run Both`.
4. UI shows in-flight state with spinner + elapsed time.
5. UI renders result cards with:
   - request payload sent
   - HTTP status + operation duration
   - normalized response body (pretty + raw JSON toggle)
   - error banner with typed code/message when failing
6. Call history keeps the last N runs for side-by-side comparison.

### Suggested Components
- `SearchPanel`: inputs + submit + last request snapshot.
- `FetchPanel`: URL input + submit + validation hints.
- `RunBothBar`: orchestrates sequential/parallel run of both operations.
- `ResultPane`: pretty + raw JSON views, copy-to-clipboard.
- `ErrorBanner`: consistent error code/message/details renderer.
- `CallHistory`: timestamped list with status, duration, and replay action.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Body parsing | Custom stream/body parser | `express.json()` | Built-in, battle-tested parser and limits |
| Input validation | Manual `if` chains | `zod` schemas | Better error detail + typed contracts |
| Request cancellation/timeout | Ad-hoc flags and race logic | `AbortController` + timeout wrapper | Standard browser primitive, predictable behavior |
| Dev API proxying (if using Vite) | Custom proxy middleware | `server.proxy` in Vite config | First-class support and less glue code |
| Browser E2E harness | Custom puppeteer scripts | Playwright test runner | Stable fixtures, reports, and cross-browser option |

**Key insight:** This phase succeeds by maximizing observability and minimizing custom infrastructure. Use built-ins and existing repo libraries to keep the UI a thin validation shell over SDK behavior.

## Common Pitfalls

### Pitfall 1: Rate-limit storms from repeated button clicks
**What goes wrong:** Multiple rapid calls trigger provider rate limits and noisy failures.  
**Why it happens:** No in-flight lock/debounce and no cooldown UX.  
**How to avoid:** Disable submit while running, add explicit retry button, and show `429` guidance in UI.  
**Warning signs:** Frequent `429` responses and inconsistent latency.

### Pitfall 2: Invalid URL confusion in fetch flow
**What goes wrong:** Users submit malformed URLs and receive vague backend errors.  
**Why it happens:** Missing pre-submit validation and poor error mapping.  
**How to avoid:** Validate URL format client-side + server-side schema validation, and return typed `VALIDATION_ERROR`.  
**Warning signs:** High proportion of 400s with generic messages.

### Pitfall 3: Latency interpreted as freeze
**What goes wrong:** Long requests look like broken UI.  
**Why it happens:** No loading state, no elapsed timer, no cancellation control.  
**How to avoid:** Running state indicator, elapsed milliseconds, and cancel/timeout path using `AbortController`.  
**Warning signs:** Users repeatedly click submit during long calls.

### Pitfall 4: Error payloads are not actionable
**What goes wrong:** UI shows "Something went wrong" without context.  
**Why it happens:** Error objects not normalized at API layer.  
**How to avoid:** Standardize error envelope (`code`, `message`, `details`, `operation`, `durationMs`).  
**Warning signs:** Debugging requires terminal logs for routine failures.

### Pitfall 5: Output is hard to inspect
**What goes wrong:** Large JSON responses become unreadable in a single block.  
**Why it happens:** No formatting controls, no collapse, no raw/pretty toggle.  
**How to avoid:** Pretty JSON by default, raw toggle, copy button, and sectioned metadata vs payload.  
**Warning signs:** Manual copy into external JSON viewers for every call.

## Test and Verification Approach

### Test Layers
- **Route unit tests (Vitest):** validation, status codes, and envelope shape for `/api/search` and `/api/fetch`.
- **Route integration tests (Vitest):** mock SDK responses/errors; assert UI-facing payload contracts.
- **UI smoke E2E (optional Playwright):** fill forms, submit, confirm running/success/error states and visible output.

### Verification Checklist for Phase Exit
- Search call can be invoked from UI and shows request + response + duration.
- Fetch call can be invoked from UI and shows request + response + duration.
- Validation errors show clear, typed messages (query/url/options).
- Timeout/network failures show explicit error state.
- Safety/compliance rejections from Phase 4 are visible and understandable in UI.
- History/replay of recent calls works for debugging comparisons.

### Operational Verification Commands
```bash
npm run typecheck
npm run test
npm run build
```

## Code Examples

Verified patterns from official sources:

### Express static frontend + JSON API
```typescript
// Source: https://expressjs.com/en/starter/static-files.html
import express from "express";

const app = express();
app.use(express.json({ limit: "100kb" }));
app.use(express.static("public"));
```

### Vite API proxy (optional architecture)
```typescript
// Source: https://vite.dev/config/server-options#server-proxy
import { defineConfig } from "vite";

export default defineConfig({
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:3000",
        changeOrigin: true,
      },
    },
  },
});
```

### Playwright bootstrap command (optional)
```bash
# Source: https://playwright.dev/docs/intro
npm init playwright@latest
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Heavy custom webpack setup for small local tools | Vite-first or no-build static for local tooling | Modernized across recent JS tooling cycles; current Vite docs emphasize simple setup | Faster startup and lower config overhead |
| Ad-hoc API request timeout logic | Standard `AbortController` cancellation | Widely available baseline since 2019 | More predictable cancellation and better UX control |
| Unstructured browser test scripts | Playwright integrated test runner/reporting | Modern E2E standard in TS/JS ecosystem | Better reproducibility and debugging artifacts |

**Deprecated/outdated:**
- Building large custom frontend plumbing for a debug console: over-investment for phase goal.
- Proxying everything manually in Express when Vite `server.proxy` already covers dev proxying (if Vite path chosen).

## Suggested Plan Slices (PLAN.md candidates)

1. **`05-01-local-api-and-contracts-PLAN.md`**  
   Define frontend request/response envelopes, add `/api/search` and `/api/fetch`, map SDK errors to typed UI-safe envelope.

2. **`05-02-dev-console-ui-surface-PLAN.md`**  
   Build minimal UI with search/fetch forms, run states, request/response panes, and error display.

3. **`05-03-observability-history-and-run-both-PLAN.md`**  
   Add call timing, request history, replay controls, and combined "Run Both" flow.

4. **`05-04-verification-and-hardening-PLAN.md`**  
   Add Vitest route tests, optional Playwright smoke flow, and phase-exit validation checklist.

## Open Questions

1. **Should `Run Both` be sequential or parallel by default?**
   - What we know: Both are needed in one validation surface.
   - What's unclear: Preferred ordering for debugging (e.g., search first then fetch top URL).
   - Recommendation: Default sequential (`search` then optional `fetch first result`) with toggle for manual independent runs.

2. **Should this phase include Vite immediately?**
   - What we know: Vite improves frontend DX but adds moving parts.
   - What's unclear: Whether expected UI complexity exceeds static HTML/JS quickly.
   - Recommendation: Start no-build; add Vite only if iteration speed becomes a real bottleneck.

3. **How much response data should be persisted in history?**
   - What we know: Full payloads are useful for debugging.
   - What's unclear: Memory impact and whether sensitive fields may appear in future payloads.
   - Recommendation: Keep recent N entries (e.g., 10) and avoid disk persistence in v1.

## Sources

### Primary (HIGH confidence)
- [Express API (`express.json`, `express.static`)](https://expressjs.com/en/api.html#express.json)
- [Express static files guide](https://expressjs.com/en/starter/static-files.html)
- [Vite Getting Started](https://vite.dev/guide/)
- [Vite server options (`server.proxy`)](https://vite.dev/config/server-options)
- [MDN AbortController](https://developer.mozilla.org/en-US/docs/Web/API/AbortController)
- [Playwright Introduction](https://playwright.dev/docs/intro)
- [Vitest Getting Started](https://vitest.dev/guide/)
- [Zod documentation](https://zod.dev/)

### Secondary (MEDIUM confidence)
- None required for core recommendations.

### Tertiary (LOW confidence)
- Web discovery for JSON viewer packages and community dashboard patterns (used only as directional context, not primary architecture basis).

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Based on current repo dependencies and official docs for Express/Zod/Vitest/Vite.
- Architecture: HIGH - Grounded in official Express/Vite docs and phase goal constraints.
- Pitfalls: MEDIUM - Derived from roadmap constraints and operational behavior patterns; should be validated during implementation.

**Research date:** 2026-03-15  
**Valid until:** 2026-04-14
