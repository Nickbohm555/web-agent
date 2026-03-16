# Phase 3: Reliability and Usage Transparency - Research

**Researched:** 2026-03-15
**Domain:** Deterministic retry/error semantics and per-call operational metadata for Node.js/TypeScript SDK retrieval primitives
**Confidence:** MEDIUM-HIGH

## Summary

Phase 3 should be implemented as a reliability layer shared by both `search(...)` and `fetch(...)`, not as tool-specific retry logic. The phase needs three hard guarantees: deterministic retry/backoff for retryable failures (especially `429`), stable typed error categories for non-retryable failures, and per-call metadata that can be inspected programmatically (timings, retries, attempts, and usage counters).

The standard implementation stack for this phase is `p-retry` for bounded retry orchestration, Node `perf_hooks` for monotonic timing, TypeScript discriminated unions for stable typed error outputs, and `pino` for structured logs with redaction. HTTP semantics must follow RFC guidance for retry safety and `Retry-After` handling. Provider payload details (Serper internals) should remain internal and mapped into canonical SDK error/metadata contracts.

**Primary recommendation:** Build one shared `core/reliability` pipeline that (1) classifies errors into retryable vs non-retryable, (2) executes deterministic retry policy with explicit `Retry-After` precedence, and (3) returns a normalized `meta` object on every successful `search`/`fetch` call.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `p-retry` | `^7.1.1` | Deterministic bounded retry/backoff with policy hooks | Provides explicit retry controls (`shouldRetry`, `shouldConsumeRetry`, `retries`, `factor`, `minTimeout`, `maxRetryTime`) and supports abort/cancel; avoids custom retry bugs. |
| `node:perf_hooks` | Node `24` LTS builtin | Monotonic timing for per-call metadata | `performance.now()` avoids wall-clock drift and is suitable for precise duration/timing telemetry. |
| TypeScript discriminated unions | TS `^5.7` | Stable typed error outputs and exhaustive handling | Official TS narrowing/exhaustiveness model yields actionable app-level branching by `kind`/`category`. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `undici` | `^7.24.3` | HTTP transport + structured error codes | Use error `code` values (e.g. `UND_ERR_CONNECT_TIMEOUT`) as classifier inputs for retryability decisions. |
| `pino` | `^10.3.1` | Structured operational logging | Emit operation, attempts, backoff, and category while redacting secrets/sensitive fields. |
| `zod` | `^4.x` | Runtime validation of options/contracts | Validate retry config and metadata shapes at API boundaries to keep outputs stable. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `p-retry` | Hand-rolled retry loop | Custom loops are easy to get wrong (budget accounting, abort propagation, `Retry-After`, deterministic behavior under tests). |
| `perf_hooks.performance.now()` | `Date.now()` | `Date.now()` is wall-clock based and can jump; duration metadata becomes unstable. |
| Typed discriminated errors | String-only error messages | Messages are not stable contracts; application code cannot branch safely without brittle parsing. |

**Installation:**
```bash
npm install p-retry pino zod undici
```

## Architecture Patterns

### Recommended Project Structure
```
src/
├── core/
│   ├── reliability/         # retry policy, backoff, classifier, Retry-After parsing
│   ├── telemetry/           # timing/usage builders and structured log events
│   └── errors/              # canonical error taxonomy + mappers
├── sdk/
│   ├── contracts/           # SearchResult/FetchResult and Error/Meta types
│   └── methods/             # search.ts and fetch.ts call shared reliability layer
└── providers/
    └── serper/              # provider adapter; never leak raw payloads outward
```

### Pattern 1: Deterministic Retry Pipeline
**What:** A single retry executor that computes the same retry schedule for identical input/config and classifies every failure before deciding to retry.
**When to use:** Every outbound network operation in `search` and `fetch`.
**Example:**
```typescript
// Source: https://www.npmjs.com/package/p-retry
import pRetry, {AbortError} from "p-retry";

type RetryClass = "retryable" | "non_retryable";

function classify(error: unknown): RetryClass {
  // App-specific mapping should inspect HTTP status + undici error.code.
  return "retryable";
}

await pRetry(runOperation, {
  retries: 4,
  factor: 2,
  minTimeout: 250,
  maxTimeout: 2_000,
  randomize: false, // deterministic schedule
  shouldRetry: ({error}) => classify(error) === "retryable",
  onFailedAttempt: ({attemptNumber, retriesLeft}) => {
    // emit structured retry telemetry
    void { attemptNumber, retriesLeft };
  }
});
```

### Pattern 2: Retry-After First, Backoff Second
**What:** For `429` and temporary overload responses, parse `Retry-After` first; if absent/invalid, use deterministic exponential backoff fallback.
**When to use:** HTTP status-driven retries (`429`, transient `5xx`, selected transport failures).
**Example:**
```typescript
// Source: RFC 9110 Retry-After - https://www.rfc-editor.org/rfc/rfc9110
function parseRetryAfterMs(value: string | null, now = Date.now()): number | null {
  if (!value) return null;
  const asSeconds = Number(value);
  if (Number.isFinite(asSeconds) && asSeconds >= 0) return asSeconds * 1000;
  const asDate = Date.parse(value);
  if (!Number.isNaN(asDate)) return Math.max(0, asDate - now);
  return null;
}
```

### Pattern 3: Typed Error Envelope with Exhaustive Handling
**What:** Return a canonical discriminated error shape with stable categories and retryability flags.
**When to use:** All failure exits from `search`/`fetch`.
**Example:**
```typescript
// Source: TypeScript handbook (discriminated unions) - https://www.typescriptlang.org/docs/handbook/2/narrowing.html#discriminated-unions
type SdkError =
  | { kind: "rate_limited"; retryable: true; retryAfterMs?: number; cause?: unknown }
  | { kind: "timeout"; retryable: true; cause?: unknown }
  | { kind: "network"; retryable: true; cause?: unknown }
  | { kind: "provider_unavailable"; retryable: true; cause?: unknown }
  | { kind: "invalid_request"; retryable: false; cause?: unknown }
  | { kind: "policy_denied"; retryable: false; cause?: unknown }
  | { kind: "content_unavailable"; retryable: false; cause?: unknown }
  | { kind: "unknown"; retryable: false; cause?: unknown };
```

### Anti-Patterns to Avoid
- **Per-method retry logic drift:** `search` and `fetch` diverge over time; use one shared reliability core.
- **Unbounded retries:** causes retry storms, unpredictable latency, and cost spikes; always cap retries + max retry time.
- **Message-parsed error handling:** branching on `error.message` text is unstable; map to explicit typed categories.
- **Returning provider/raw transport errors directly:** leaks internals and creates contract churn.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Retry/backoff orchestration | Custom `while`/`setTimeout` loops | `p-retry` | Built-in retry budgeting, abort support, and policy hooks reduce edge-case bugs. |
| Monotonic duration tracking | Wall-clock deltas with `Date.now()` | `performance.now()` from `node:perf_hooks` | Stable duration math even if system clock changes. |
| Transport error categorization | Ad-hoc regex on error messages | `undici` error `code` mapping + HTTP status mapping | Machine-stable classification surface for deterministic behavior. |
| Secret-safe operational logs | Manual object cloning/deletion | `pino` with `redact` paths | Redaction is standardized and lower risk than hand-written sanitizers. |

**Key insight:** reliability defects usually come from subtle edge cases (retry budget handling, timing drift, error ambiguity). Standard primitives are cheaper and more predictable than custom implementations.

## Common Pitfalls

### Pitfall 1: Non-deterministic backoff in tests and production
**What goes wrong:** Retry timing changes run-to-run, producing flaky tests and confusing latency behavior.
**Why it happens:** Random jitter is enabled without deterministic policy requirements.
**How to avoid:** Use deterministic defaults (`randomize: false`) and explicit retry schedule config; if jitter is later needed, make it opt-in and testable.
**Warning signs:** Same failing input yields different retry timestamps/attempt counts across runs.

### Pitfall 2: Ignoring `Retry-After` semantics
**What goes wrong:** Clients hammer providers after `429`/temporary overload responses.
**Why it happens:** Backoff logic ignores server guidance or parses only one format.
**How to avoid:** Parse both allowed formats (`delay-seconds` and `HTTP-date`) and apply as first priority.
**Warning signs:** Immediate retries after `429`; repeated minute-boundary throttling.

### Pitfall 3: Error categories too coarse or unstable
**What goes wrong:** App code cannot take actionable branches (retry, fallback, prompt user fix).
**Why it happens:** Exposing generic `Error` with freeform messages.
**How to avoid:** Enforce discriminated union categories with `retryable` and optional `retryAfterMs` hints.
**Warning signs:** Consumer code checking `includes("timeout")` or provider-specific text.

### Pitfall 4: Metadata only in logs, not return contract
**What goes wrong:** Developers cannot inspect retry/timing/usage data programmatically.
**Why it happens:** Observability treated as logging concern instead of API contract concern.
**How to avoid:** Include `meta` object in every successful response with stable fields.
**Warning signs:** Need to parse logs to answer "how many retries did this call take?".

## Code Examples

Verified patterns from official sources:

### Deterministic retry with failure hooks
```typescript
// Source: https://www.npmjs.com/package/p-retry
import pRetry from "p-retry";

const value = await pRetry(run, {
  retries: 3,
  factor: 2,
  minTimeout: 200,
  randomize: false,
  onFailedAttempt: ({error, attemptNumber, retriesLeft}) => {
    logger.warn({error, attemptNumber, retriesLeft}, "operation retry");
  }
});
```

### Monotonic call timing metadata
```typescript
// Source: https://nodejs.org/api/perf_hooks.html
import {performance} from "node:perf_hooks";

const started = performance.now();
const result = await runOperation();
const elapsedMs = performance.now() - started;
```

### Exhaustive typed error handling
```typescript
// Source: https://www.typescriptlang.org/docs/handbook/2/narrowing.html#discriminated-unions
function handleError(err: SdkError): void {
  switch (err.kind) {
    case "rate_limited":
    case "timeout":
    case "network":
    case "provider_unavailable":
    case "invalid_request":
    case "policy_denied":
    case "content_unavailable":
    case "unknown":
      return;
    default: {
      const _exhaustive: never = err;
      return _exhaustive;
    }
  }
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Ad-hoc retries in each code path | Shared retry middleware with typed classification | Ongoing standardization in modern TS SDKs | Consistent behavior and easier testability |
| String-based error handling | Discriminated union error contracts | Mature TS narrowing/exhaustiveness usage | Safer app-side branching and fewer regressions |
| Wall-clock timing (`Date.now`) | Monotonic timing (`performance.now`) | Longstanding best practice in modern runtimes | Reliable latency/usage metrics |
| Unstructured logs with manual scrubbing | Structured JSON logs + redaction config | Mature pino operational pattern | Lower secret leakage risk and better observability |

**Deprecated/outdated:**
- Parsing retry behavior from freeform provider messages: too unstable for deterministic guarantees.
- Returning raw provider payload as error/result surface: violates SDK contract stability and couples consumers to provider internals.

## Open Questions

1. **Serper rate-limit metadata surface**
   - What we know: Public Serper material documents QPS tiers and `429` behavior; RFC semantics for `Retry-After` are clear.
   - What's unclear: Whether Serper provides consistent rate-limit headers/counters beyond status code in all failure modes.
   - Recommendation: In planning, require fallback behavior that works without provider-specific rate headers (`429` + deterministic backoff), and treat any provider headers as optional enhancements.

2. **Metadata contract strictness for v1**
   - What we know: Requirement REL-02 mandates inspectable per-call usage/timing metadata.
   - What's unclear: Minimum mandatory metadata field set for GA (e.g., include attempts, retries, cache, phase timings, provider usage tokens/credits if available).
   - Recommendation: Lock a minimal required schema in planning (`requestId`, `operation`, `startedAt`, `durationMs`, `attempts`, `retries`, `cacheHit`, `timings`) and permit optional provider-specific usage fields under a namespaced key.

## Sources

### Primary (HIGH confidence)
- [RFC 9110](https://www.rfc-editor.org/rfc/rfc9110) - `Retry-After` semantics and retry safety context (idempotency guidance).
- [RFC 6585](https://www.rfc-editor.org/rfc/rfc6585) - `429 Too Many Requests` semantics.
- [p-retry npm docs](https://www.npmjs.com/package/p-retry) - deterministic retry/backoff API and hooks.
- [Node `perf_hooks` docs](https://nodejs.org/api/perf_hooks.html) - monotonic timing APIs for duration measurement.
- [TypeScript Handbook: Discriminated Unions](https://www.typescriptlang.org/docs/handbook/2/narrowing.html#discriminated-unions) - stable typed union/error handling patterns.
- [Undici Errors reference](https://raw.githubusercontent.com/nodejs/undici/main/docs/docs/api/Errors.md) - transport error code taxonomy for mapping.
- [Pino redaction docs](https://raw.githubusercontent.com/pinojs/pino/main/docs/redaction.md) - secret-safe structured logging patterns.

### Secondary (MEDIUM confidence)
- [Serper homepage/FAQ](https://serper.dev/) - provider throughput and behavior context for planning assumptions.

### Tertiary (LOW confidence)
- Web ecosystem scans for 2026 TypeScript SDK error-taxonomy trends (used for directional context only; not normative).

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - built on official library/runtime docs and RFCs.
- Architecture: MEDIUM-HIGH - strongly grounded in standards and library capabilities, with some project-specific contract choices.
- Pitfalls: MEDIUM - technically consistent with standards but some provider-specific behavior remains under-documented publicly.

**Research date:** 2026-03-15
**Valid until:** 2026-04-14 (30 days)
