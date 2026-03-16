import { describe, expect, it } from "vitest";

import { createFetchSafetyError } from "../../core/errors/fetch-safety-error.js";
import { evaluateSafetyPreflight } from "../../core/policy/safety-decision.js";
import { evaluateUrlPolicy } from "../../core/policy/url-policy.js";

describe("url preflight policy", () => {
  it("allows safe http and https urls with normalized target metadata", () => {
    expect(evaluateUrlPolicy("https://Example.com/articles?id=1#summary")).toEqual({
      stage: "url_preflight",
      outcome: "allow",
      target: {
        url: "https://example.com/articles?id=1",
        scheme: "https",
        hostname: "example.com",
        port: 443,
      },
    });

    expect(evaluateSafetyPreflight("http://example.com:8080/path")).toEqual({
      stage: "url_preflight",
      outcome: "allow",
      target: {
        url: "http://example.com:8080/path",
        scheme: "http",
        hostname: "example.com",
        port: 8080,
      },
    });
  });

  it("denies unsupported schemes deterministically", () => {
    expect(evaluateUrlPolicy("file:///tmp/data.txt")).toEqual({
      stage: "url_preflight",
      outcome: "deny",
      reason: "UNSAFE_SCHEME",
      target: {
        url: "file:///tmp/data.txt",
        scheme: "file",
        hostname: null,
        port: null,
      },
    });
  });

  it("denies urls with inline credentials", () => {
    expect(evaluateUrlPolicy("https://user:secret@example.com/report")).toEqual({
      stage: "url_preflight",
      outcome: "deny",
      reason: "URL_HAS_CREDENTIALS",
      target: {
        url: "https://user:secret@example.com/report",
        scheme: "https",
        hostname: "example.com",
        port: 443,
      },
    });
  });

  it("fails closed on malformed urls and preserves raw candidate hints", () => {
    expect(evaluateUrlPolicy("not a valid url")).toEqual({
      stage: "url_preflight",
      outcome: "deny",
      reason: "MALFORMED_URL",
      target: {
        url: "not a valid url",
        scheme: "",
        hostname: null,
        port: null,
      },
    });
  });

  it("denies parsed urls whose host is structurally empty", () => {
    expect(evaluateUrlPolicy("http://./internal")).toEqual({
      stage: "url_preflight",
      outcome: "deny",
      reason: "INVALID_HOST",
      target: {
        url: "http://./internal",
        scheme: "http",
        hostname: ".",
        port: 80,
      },
    });
  });

  it("maps deny decisions to typed public fetch errors without changing machine-readable fields", () => {
    const decision = evaluateSafetyPreflight("https://user:secret@example.com/report");

    expect(decision.outcome).toBe("deny");

    if (decision.outcome !== "deny") {
      throw new Error("expected deny decision");
    }

    const error = createFetchSafetyError({
      decision,
      attempts: 1,
      retries: 0,
      timings: {
        safetyMs: 2,
      },
    });

    expect(error).toMatchObject({
      name: "SdkError",
      kind: "policy_denied",
      retryable: false,
      code: "POLICY_DENIED",
      operation: "fetch",
      stage: "url_preflight",
      reason: "URL_HAS_CREDENTIALS",
      decision: {
        stage: "url_preflight",
        outcome: "deny",
        reason: "URL_HAS_CREDENTIALS",
        target: {
          url: "https://user:secret@example.com/report",
          scheme: "https",
          hostname: "example.com",
          port: 443,
        },
      },
      fallbackReason: null,
      meta: {
        operation: "fetch",
        attempts: 1,
        retries: 0,
        cacheHit: false,
        durationMs: expect.any(Number),
        timings: {
          safetyMs: 2,
        },
      },
      metadata: {
        finalUrl: "https://user:secret@example.com/report",
        contentType: null,
        statusCode: null,
        decisions: {
          safety: {
            stage: "url_preflight",
            outcome: "deny",
            reason: "URL_HAS_CREDENTIALS",
            target: {
              url: "https://user:secret@example.com/report",
              scheme: "https",
              hostname: "example.com",
              port: 443,
            },
          },
          compliance: null,
        },
      },
    });
  });
});
