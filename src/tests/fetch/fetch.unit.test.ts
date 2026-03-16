import { describe, expect, it, vi } from "vitest";

import { extractContent } from "../../scraper/extract.js";
import { runFetchOrchestrator } from "../../scraper/orchestrator.js";
import { runHttpWorker } from "../../scraper/http-worker.js";
import type { RobotsComplianceResult } from "../../scraper/robots/evaluator.js";

describe("fetch task 1 primitives", () => {
  it("blocks disallowed targets before content fetch runs", async () => {
    const runHttpWorkerFn = vi.fn();

    await expect(
      runFetchOrchestrator("https://example.com/private", {
        evaluateRobotsComplianceFn: vi.fn(async () => createDeniedRobotsResult("https://example.com/private")),
        runHttpWorkerFn,
      }),
    ).rejects.toMatchObject({
      kind: "policy_denied",
      stage: "robots",
      reason: "ROBOTS_DENY",
    });
    expect(runHttpWorkerFn).not.toHaveBeenCalled();
  });

  it("retries retryable transport failures with a bounded attempt count", async () => {
    const transportError = Object.assign(new Error("socket timeout"), {
      code: "ETIMEDOUT",
    });
    const requestFn = vi
      .fn()
      .mockRejectedValueOnce(transportError)
      .mockRejectedValueOnce(transportError)
      .mockResolvedValue({
        statusCode: 200,
        headers: {
          "content-type": "text/html; charset=utf-8",
        },
        context: {
          history: [],
        },
        body: {
          text: async () => "<html><body>ok</body></html>",
        },
      });

    const result = await runHttpWorker("https://example.com/article", {
      requestFn: requestFn as never,
      timeoutMs: 100,
    });

    expect(result.state).toBe("OK");
    expect(result.meta).toMatchObject({
      attempts: 3,
      retries: 2,
    });
    expect(requestFn).toHaveBeenCalledTimes(3);
  });

  it("returns a typed unsupported status result without retrying permanent 4xx failures", async () => {
    const requestFn = vi.fn().mockResolvedValue({
      statusCode: 403,
      headers: {},
      context: {
        history: [],
      },
      body: {
        text: async () => "forbidden",
      },
    });

    const result = await runHttpWorker("https://example.com/forbidden", {
      requestFn: requestFn as never,
    });

    expect(result).toMatchObject({
      state: "HTTP_STATUS_UNSUPPORTED",
      url: "https://example.com/forbidden",
      finalUrl: "https://example.com/forbidden",
      statusCode: 403,
      contentType: null,
      body: null,
      errorClass: "SdkError",
      errorKind: "invalid_request",
      retryable: false,
    });
    expect(result.meta).toMatchObject({
      attempts: 1,
      retries: 0,
    });
    expect(requestFn).toHaveBeenCalledTimes(1);
  });

  it("extracts normalized text and markdown from successful HTML fetches", async () => {
    const response = await runFetchOrchestrator("https://example.com/article", {
      evaluateRobotsComplianceFn: vi.fn(async () => createAllowedRobotsResult("https://example.com/article")),
      runHttpWorkerFn: vi.fn(async () => ({
        state: "OK" as const,
        url: "https://example.com/article",
        finalUrl: "https://example.com/article",
        statusCode: 200,
        contentType: "text/html; charset=utf-8",
        body: `
          <html>
            <head><title>Example Article</title></head>
            <body>
              <main>
                <h1>Example Article</h1>
                <p>This article contains enough text to satisfy the quality threshold for deterministic extraction output.</p>
                <p>It keeps the HTTP-first flow intact and provides markdown content for callers.</p>
              </main>
            </body>
          </html>
        `,
        meta: {
          attempts: 1,
          retries: 0,
          durationMs: 5,
        },
      })),
    });

    expect(response).toMatchObject({
      url: "https://example.com/article",
      meta: {
        operation: "fetch",
        durationMs: expect.any(Number),
        attempts: 1,
        retries: 0,
        cacheHit: false,
      },
      metadata: {
        finalUrl: "https://example.com/article",
        contentType: "text/html; charset=utf-8",
        statusCode: 200,
        decisions: {
          safety: {
            stage: "network_preflight",
            outcome: "allow",
            target: {
              url: "https://example.com/article",
              scheme: "https",
              hostname: "example.com",
              port: 443,
            },
          },
          compliance: {
            stage: "robots",
            outcome: "allow",
            reason: "ROBOTS_ALLOW",
            target: {
              url: "https://example.com/article",
              scheme: "https",
              hostname: "example.com",
              port: 443,
            },
          },
        },
      },
      fallbackReason: null,
    });
    expect(response.text).toContain("Example Article");
    expect(response.markdown).toContain("Example Article");
  });

  it("throws a typed fetch error when HTTP retrieval fails", async () => {
    const evaluateRobotsComplianceFn = vi.fn(
      async () => createAllowedRobotsResult("https://example.com/article"),
    );
    const runHttpWorkerFn = vi.fn(async () => ({
      state: "NETWORK_ERROR" as const,
      url: "https://example.com/article",
      finalUrl: null,
      statusCode: null,
      contentType: null,
      body: null,
      errorClass: "SdkError",
      errorKind: "network" as const,
      retryable: true,
      meta: {
        attempts: 3,
        retries: 2,
        durationMs: 12,
      },
    }));

    await expect(
      runFetchOrchestrator("https://example.com/article", {
        evaluateRobotsComplianceFn,
        runHttpWorkerFn,
      }),
    ).rejects.toMatchObject({
      name: "SdkError",
      kind: "network",
      retryable: true,
      attemptNumber: 3,
      operation: "fetch",
      fallbackReason: "network-error",
      meta: {
        operation: "fetch",
        durationMs: expect.any(Number),
        attempts: 3,
        retries: 2,
        cacheHit: false,
        timings: {
          robotsMs: expect.any(Number),
          httpMs: expect.any(Number),
        },
      },
      metadata: {
        finalUrl: "https://example.com/article",
        contentType: null,
        statusCode: null,
        decisions: {
          safety: {
            stage: "network_preflight",
            outcome: "allow",
            target: {
              url: "https://example.com/article",
              scheme: "https",
              hostname: "example.com",
              port: 443,
            },
          },
          compliance: {
            stage: "robots",
            outcome: "allow",
            reason: "ROBOTS_ALLOW",
            target: {
              url: "https://example.com/article",
              scheme: "https",
              hostname: "example.com",
              port: 443,
            },
          },
        },
      },
    });
    expect(evaluateRobotsComplianceFn).toHaveBeenCalledBefore(runHttpWorkerFn);
  });

  it("returns low-content-quality when extraction output is too thin", async () => {
    const response = await runFetchOrchestrator("https://example.com/thin", {
      evaluateRobotsComplianceFn: vi.fn(async () => createAllowedRobotsResult("https://example.com/thin")),
      runHttpWorkerFn: vi.fn(async () => ({
        state: "OK" as const,
        url: "https://example.com/thin",
        finalUrl: "https://example.com/thin",
        statusCode: 200,
        contentType: "text/html",
        body: "<html><body><main><p>Too short.</p></main></body></html>",
        meta: {
          attempts: 1,
          retries: 0,
          durationMs: 2,
        },
      })),
    });

    expect(response).toEqual({
      url: "https://example.com/thin",
      text: "Too short.",
      markdown: "Too short.",
      meta: {
        operation: "fetch",
        durationMs: expect.any(Number),
        attempts: 1,
        retries: 0,
        cacheHit: false,
        timings: {
          safetyMs: expect.any(Number),
          robotsMs: expect.any(Number),
          httpMs: expect.any(Number),
          extractionMs: expect.any(Number),
        },
        usage: {
          content: {
            textChars: 10,
            markdownChars: 10,
          },
        },
      },
      metadata: {
        finalUrl: "https://example.com/thin",
        contentType: "text/html",
        statusCode: 200,
        decisions: {
          safety: {
            stage: "network_preflight",
            outcome: "allow",
            target: {
              url: "https://example.com/thin",
              scheme: "https",
              hostname: "example.com",
              port: 443,
            },
          },
          compliance: {
            stage: "robots",
            outcome: "allow",
            reason: "ROBOTS_ALLOW",
            target: {
              url: "https://example.com/thin",
              scheme: "https",
              hostname: "example.com",
              port: 443,
            },
          },
        },
      },
      fallbackReason: "low-content-quality",
    });
  });

  it("marks unsupported content types as browser-required", () => {
    expect(extractContent("plain text", "text/plain")).toEqual({
      state: "UNSUPPORTED_CONTENT_TYPE",
      text: "",
      markdown: "",
      title: null,
    });
  });
});

function createAllowedRobotsResult(targetUrl: string): RobotsComplianceResult {
  return {
    outcome: "ALLOW",
    decision: {
      stage: "robots",
      outcome: "allow",
      reason: "ROBOTS_ALLOW",
      target: {
        url: targetUrl,
        scheme: "https",
        hostname: "example.com",
        port: 443,
      },
    },
    target: {
      url: targetUrl,
      scheme: "https",
      hostname: "example.com",
      port: 443,
    },
    userAgent: "web-agent-bot",
    crawlDelaySeconds: null,
    reason: {
      code: "ROBOTS_ALLOW",
      detail: "ROBOTS_RULE_ALLOW",
      robotsUrl: "https://example.com/robots.txt",
      httpStatus: 200,
      fetchedAt: "2026-03-15T00:00:00.000Z",
      errorClass: null,
    },
  };
}

function createDeniedRobotsResult(targetUrl: string): RobotsComplianceResult {
  return {
    outcome: "DENY",
    decision: {
      stage: "robots",
      outcome: "deny",
      reason: "ROBOTS_DENY",
      target: {
        url: targetUrl,
        scheme: "https",
        hostname: "example.com",
        port: 443,
      },
    },
    target: {
      url: targetUrl,
      scheme: "https",
      hostname: "example.com",
      port: 443,
    },
    userAgent: "web-agent-bot",
    crawlDelaySeconds: null,
    reason: {
      code: "ROBOTS_DENY",
      detail: "ROBOTS_RULE_DENY",
      robotsUrl: "https://example.com/robots.txt",
      httpStatus: 200,
      fetchedAt: "2026-03-15T00:00:00.000Z",
      errorClass: null,
    },
  };
}
