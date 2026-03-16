import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { describe, expect, it, vi } from "vitest";

import { runFetchOrchestrator } from "../../scraper/orchestrator.js";
import {
  evaluateRobotsCompliance,
  type RobotsComplianceResult,
} from "../../scraper/robots/evaluator.js";
import type { ResolveAndClassifyResult } from "../../core/network/resolve-and-classify.js";
import type { SafetyDecision } from "../../sdk/contracts/safety.js";

const fixturesDir = fileURLToPath(new URL("../fixtures/robots/", import.meta.url));

describe("fetch safety compliance integration", () => {
  it("returns explicit ALLOW outcomes for permissive robots files", async () => {
    const body = await readFixture("allow-all.txt");
    const requestFn = vi.fn(async () => ({
      statusCode: 200,
      headers: {},
      body: {
        text: async () => body,
      },
    }));

    const result = await evaluateRobotsCompliance("https://example.com/article", {
      requestFn: requestFn as never,
      userAgent: "web-agent-bot",
    });

    expect(result).toEqual({
      outcome: "ALLOW",
      decision: {
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
      target: {
        url: "https://example.com/article",
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
        fetchedAt: expect.any(String),
        errorClass: null,
      },
    });
  });

  it("returns explicit DENY outcomes for disallowed paths", async () => {
    const body = await readFixture("deny-path.txt");
    const requestFn = vi.fn(async () => ({
      statusCode: 200,
      headers: {},
      body: {
        text: async () => body,
      },
    }));

    const result = await evaluateRobotsCompliance("https://example.com/private", {
      requestFn: requestFn as never,
      userAgent: "web-agent-bot",
    });

    expect(result).toEqual({
      outcome: "DENY",
      decision: {
        stage: "robots",
        outcome: "deny",
        reason: "ROBOTS_DENY",
        target: {
          url: "https://example.com/private",
          scheme: "https",
          hostname: "example.com",
          port: 443,
        },
      },
      target: {
        url: "https://example.com/private",
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
        fetchedAt: expect.any(String),
        errorClass: null,
      },
    });
  });

  it("returns explicit UNKNOWN outcomes when unavailable robots are configured to fail open", async () => {
    const requestFn = vi.fn(async () => {
      throw Object.assign(new Error("temporary reset"), { name: "SocketError" });
    });

    const result = await evaluateRobotsCompliance("https://example.com/public", {
      requestFn: requestFn as never,
      userAgent: "web-agent-bot",
      failClosedOnUnavailable: false,
    });

    expect(result).toEqual({
      outcome: "UNKNOWN",
      decision: {
        stage: "robots",
        outcome: "unknown",
        reason: "ROBOTS_UNKNOWN",
        target: {
          url: "https://example.com/public",
          scheme: "https",
          hostname: "example.com",
          port: 443,
        },
      },
      target: {
        url: "https://example.com/public",
        scheme: "https",
        hostname: "example.com",
        port: 443,
      },
      userAgent: "web-agent-bot",
      crawlDelaySeconds: null,
      reason: {
        code: "ROBOTS_UNKNOWN",
        detail: "ROBOTS_FETCH_FAILED",
        robotsUrl: "https://example.com/robots.txt",
        httpStatus: null,
        fetchedAt: expect.any(String),
        errorClass: "SocketError",
      },
    });
  });

  it("returns explicit UNAVAILABLE outcomes when robots retrieval fails closed", async () => {
    const requestFn = vi.fn(async () => {
      throw Object.assign(new Error("socket timeout"), { name: "TimeoutError" });
    });

    const result = await evaluateRobotsCompliance("https://example.com/article", {
      requestFn: requestFn as never,
      userAgent: "web-agent-bot",
    });

    expect(result).toEqual({
      outcome: "UNAVAILABLE",
      decision: {
        stage: "robots",
        outcome: "unavailable",
        reason: "ROBOTS_UNAVAILABLE",
        target: {
          url: "https://example.com/article",
          scheme: "https",
          hostname: "example.com",
          port: 443,
        },
      },
      target: {
        url: "https://example.com/article",
        scheme: "https",
        hostname: "example.com",
        port: 443,
      },
      userAgent: "web-agent-bot",
      crawlDelaySeconds: null,
      reason: {
        code: "ROBOTS_UNAVAILABLE",
        detail: "ROBOTS_FETCH_FAILED",
        robotsUrl: "https://example.com/robots.txt",
        httpStatus: null,
        fetchedAt: expect.any(String),
        errorClass: "TimeoutError",
      },
    });
  });

  it("surfaces url preflight denies through the public fetch contract and never reaches downstream stages", async () => {
    vi.resetModules();
    const resolveAndClassifyTarget = vi.fn();
    const evaluateRobotsCompliance = vi.fn();
    const runHttpWorker = vi.fn();

    vi.doMock("../../core/network/resolve-and-classify.js", () => ({
      resolveAndClassifyTarget,
    }));
    vi.doMock("../../scraper/robots/evaluator.js", () => ({
      evaluateRobotsCompliance,
    }));
    vi.doMock("../../scraper/http-worker.js", () => ({
      runHttpWorker,
    }));

    const { fetch } = await import("../../sdk/fetch.js");

    await expect(
      fetch("https://user:secret@example.com/article", {
        fresh: true,
      }),
    ).rejects.toMatchObject({
      name: "SdkError",
      kind: "policy_denied",
      operation: "fetch",
      stage: "url_preflight",
      reason: "URL_HAS_CREDENTIALS",
      fallbackReason: null,
      metadata: {
        finalUrl: "https://user:secret@example.com/article",
        decisions: {
          safety: {
            stage: "url_preflight",
            outcome: "deny",
            reason: "URL_HAS_CREDENTIALS",
          },
          compliance: null,
        },
      },
    });

    expect(resolveAndClassifyTarget).not.toHaveBeenCalled();
    expect(evaluateRobotsCompliance).not.toHaveBeenCalled();
    expect(runHttpWorker).not.toHaveBeenCalled();
  });

  it("surfaces ssrf denies through the public fetch contract and never reaches robots or http", async () => {
    vi.resetModules();
    const resolveAndClassifyTarget = vi.fn(
      async (): Promise<ResolveAndClassifyResult> => ({
        outcome: "deny",
        decision: {
          stage: "network_preflight",
          outcome: "deny",
          reason: "SSRF_BLOCKED_IP",
          target: {
            url: "https://example.com/article",
            scheme: "https",
            hostname: "example.com",
            port: 443,
          },
        },
        resolvedAddresses: [
          {
            address: "127.0.0.1",
            family: 4,
            normalized: "127.0.0.1",
            classification: "loopback",
            outcome: "deny",
          },
        ],
        resolverErrorCode: null,
      }),
    );
    const evaluateRobotsCompliance = vi.fn();
    const runHttpWorker = vi.fn();

    vi.doMock("../../core/network/resolve-and-classify.js", () => ({
      resolveAndClassifyTarget,
    }));
    vi.doMock("../../scraper/robots/evaluator.js", () => ({
      evaluateRobotsCompliance,
    }));
    vi.doMock("../../scraper/http-worker.js", () => ({
      runHttpWorker,
    }));

    const { fetch } = await import("../../sdk/fetch.js");

    await expect(
      fetch("https://example.com/article", {
        fresh: true,
      }),
    ).rejects.toMatchObject({
      name: "SdkError",
      kind: "policy_denied",
      operation: "fetch",
      stage: "network_preflight",
      reason: "SSRF_BLOCKED_IP",
      fallbackReason: null,
      metadata: {
        finalUrl: "https://example.com/article",
        decisions: {
          safety: {
            stage: "network_preflight",
            outcome: "deny",
            reason: "SSRF_BLOCKED_IP",
          },
          compliance: null,
        },
      },
    });

    expect(evaluateRobotsCompliance).not.toHaveBeenCalled();
    expect(runHttpWorker).not.toHaveBeenCalled();
  });

  it("surfaces robots deny decisions through the public fetch contract and never reaches http", async () => {
    vi.resetModules();
    const resolveAndClassifyTarget = vi.fn(
      async (): Promise<ResolveAndClassifyResult> => ({
        outcome: "allow",
        decision: {
          stage: "network_preflight",
          outcome: "allow",
          target: {
            url: "https://example.com/private",
            scheme: "https",
            hostname: "example.com",
            port: 443,
          },
        },
        resolvedAddresses: [
          {
            address: "93.184.216.34",
            family: 4,
            normalized: "93.184.216.34",
            classification: "public",
            outcome: "allow",
          },
        ],
      }),
    );
    const evaluateRobotsCompliance = vi.fn(
      async () => createRobotsResult("DENY", "https://example.com/private"),
    );
    const runHttpWorker = vi.fn();

    vi.doMock("../../core/network/resolve-and-classify.js", () => ({
      resolveAndClassifyTarget,
    }));
    vi.doMock("../../scraper/robots/evaluator.js", () => ({
      evaluateRobotsCompliance,
    }));
    vi.doMock("../../scraper/http-worker.js", () => ({
      runHttpWorker,
    }));

    const { fetch } = await import("../../sdk/fetch.js");

    await expect(
      fetch("https://example.com/private", {
        fresh: true,
      }),
    ).rejects.toMatchObject({
      name: "SdkError",
      kind: "policy_denied",
      operation: "fetch",
      stage: "robots",
      reason: "ROBOTS_DENY",
      fallbackReason: null,
      metadata: {
        finalUrl: "https://example.com/private",
        decisions: {
          safety: {
            stage: "network_preflight",
            outcome: "allow",
          },
          compliance: {
            stage: "robots",
            outcome: "deny",
            reason: "ROBOTS_DENY",
          },
        },
      },
    });

    expect(evaluateRobotsCompliance).toHaveBeenCalledTimes(1);
    expect(runHttpWorker).not.toHaveBeenCalled();
  });

  it("short-circuits before robots and http when url safety preflight denies", async () => {
    const evaluateRobotsComplianceFn = vi.fn();
    const runHttpWorkerFn = vi.fn();

    await expect(
      runFetchOrchestrator("https://example.com/article", {
        evaluateSafetyPreflightFn: vi.fn(
          (): SafetyDecision => ({
            stage: "url_preflight",
            outcome: "deny",
            reason: "URL_HAS_CREDENTIALS",
            target: {
              url: "https://user:secret@example.com/article",
              scheme: "https",
              hostname: "example.com",
              port: 443,
            },
          }),
        ),
        evaluateRobotsComplianceFn,
        runHttpWorkerFn,
      }),
    ).rejects.toMatchObject({
      kind: "policy_denied",
      stage: "url_preflight",
      reason: "URL_HAS_CREDENTIALS",
      metadata: {
        finalUrl: "https://user:secret@example.com/article",
        decisions: {
          safety: {
            stage: "url_preflight",
            outcome: "deny",
            reason: "URL_HAS_CREDENTIALS",
          },
          compliance: null,
        },
      },
    });

    expect(evaluateRobotsComplianceFn).not.toHaveBeenCalled();
    expect(runHttpWorkerFn).not.toHaveBeenCalled();
  });

  it("short-circuits before robots and http when network safety preflight denies", async () => {
    const evaluateRobotsComplianceFn = vi.fn();
    const runHttpWorkerFn = vi.fn();

    await expect(
      runFetchOrchestrator("https://example.com/article", {
        resolveAndClassifyTargetFn: vi.fn(
          async (): Promise<ResolveAndClassifyResult> => ({
            outcome: "deny",
            decision: {
              stage: "network_preflight",
              outcome: "deny",
              reason: "SSRF_BLOCKED_IP",
              target: {
                url: "https://example.com/article",
                scheme: "https",
                hostname: "example.com",
                port: 443,
              },
            },
            resolvedAddresses: [
              {
                address: "127.0.0.1",
                family: 4,
                normalized: "127.0.0.1",
                classification: "loopback",
                outcome: "deny",
              },
            ],
            resolverErrorCode: null,
          }),
        ),
        evaluateRobotsComplianceFn,
        runHttpWorkerFn,
      }),
    ).rejects.toMatchObject({
      kind: "policy_denied",
      stage: "network_preflight",
      reason: "SSRF_BLOCKED_IP",
      metadata: {
        finalUrl: "https://example.com/article",
        decisions: {
          safety: {
            stage: "network_preflight",
            outcome: "deny",
            reason: "SSRF_BLOCKED_IP",
          },
          compliance: null,
        },
      },
    });

    expect(evaluateRobotsComplianceFn).not.toHaveBeenCalled();
    expect(runHttpWorkerFn).not.toHaveBeenCalled();
  });

  it("short-circuits before http when robots compliance denies", async () => {
    const runHttpWorkerFn = vi.fn();

    await expect(
      runFetchOrchestrator("https://example.com/private", {
        evaluateRobotsComplianceFn: vi.fn(
          async () => createRobotsResult("DENY", "https://example.com/private"),
        ),
        runHttpWorkerFn,
      }),
    ).rejects.toMatchObject({
      kind: "policy_denied",
      stage: "robots",
      reason: "ROBOTS_DENY",
      metadata: {
        finalUrl: "https://example.com/private",
        decisions: {
          safety: {
            stage: "network_preflight",
            outcome: "allow",
          },
          compliance: {
            stage: "robots",
            outcome: "deny",
            reason: "ROBOTS_DENY",
          },
        },
      },
    });

    expect(runHttpWorkerFn).not.toHaveBeenCalled();
  });

  it("surfaces robots unavailable as an explicit compliance block before http", async () => {
    const runHttpWorkerFn = vi.fn();

    await expect(
      runFetchOrchestrator("https://example.com/article", {
        evaluateRobotsComplianceFn: vi.fn(
          async () => createRobotsResult("UNAVAILABLE", "https://example.com/article"),
        ),
        runHttpWorkerFn,
      }),
    ).rejects.toMatchObject({
      kind: "policy_denied",
      stage: "robots",
      reason: "ROBOTS_UNAVAILABLE",
      metadata: {
        finalUrl: "https://example.com/article",
        decisions: {
          safety: {
            stage: "network_preflight",
            outcome: "allow",
          },
          compliance: {
            stage: "robots",
            outcome: "unavailable",
            reason: "ROBOTS_UNAVAILABLE",
          },
        },
      },
    });

    expect(runHttpWorkerFn).not.toHaveBeenCalled();
  });

  it("returns allowed fetches with explicit safety and compliance decisions", async () => {
    const runHttpWorkerFn = vi.fn(async () => ({
      state: "OK" as const,
      url: "https://example.com/article",
      finalUrl: "https://example.com/article",
      statusCode: 200,
      contentType: "text/html; charset=utf-8",
      body: "<html><body><main><p>This article has enough words to clear deterministic extraction output in the compliance integration test.</p><p>It also adds a second paragraph so the extractor returns a normal success instead of the low-content fallback path during this pipeline verification.</p></main></body></html>",
      meta: {
        attempts: 1,
        retries: 0,
        durationMs: 3,
      },
    }));

    const response = await runFetchOrchestrator("https://example.com/article", {
      evaluateRobotsComplianceFn: vi.fn(
        async () => createRobotsResult("ALLOW", "https://example.com/article"),
      ),
      runHttpWorkerFn,
    });

    expect(response).toMatchObject({
      url: "https://example.com/article",
      metadata: {
        finalUrl: "https://example.com/article",
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

    expect(runHttpWorkerFn).toHaveBeenCalledTimes(1);
  });
});

async function readFixture(name: string): Promise<string> {
  return readFile(new URL(name, `file://${fixturesDir}/`), "utf8");
}

function createRobotsResult(
  outcome: "ALLOW" | "DENY" | "UNAVAILABLE",
  targetUrl: string,
): RobotsComplianceResult {
  const normalizedTarget = {
    url: targetUrl,
    scheme: "https",
    hostname: "example.com",
    port: 443,
  } as const;

  if (outcome === "DENY") {
    return {
      outcome,
      decision: {
        stage: "robots",
        outcome: "deny",
        reason: "ROBOTS_DENY",
        target: normalizedTarget,
      },
      target: normalizedTarget,
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

  if (outcome === "UNAVAILABLE") {
    return {
      outcome,
      decision: {
        stage: "robots",
        outcome: "unavailable",
        reason: "ROBOTS_UNAVAILABLE",
        target: normalizedTarget,
      },
      target: normalizedTarget,
      userAgent: "web-agent-bot",
      crawlDelaySeconds: null,
      reason: {
        code: "ROBOTS_UNAVAILABLE",
        detail: "ROBOTS_FETCH_FAILED",
        robotsUrl: "https://example.com/robots.txt",
        httpStatus: null,
        fetchedAt: "2026-03-15T00:00:00.000Z",
        errorClass: "TimeoutError",
      },
    };
  }

  return {
    outcome,
    decision: {
      stage: "robots",
      outcome: "allow",
      reason: "ROBOTS_ALLOW",
      target: normalizedTarget,
    },
    target: normalizedTarget,
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
