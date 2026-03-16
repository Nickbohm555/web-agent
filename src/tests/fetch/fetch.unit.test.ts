import { describe, expect, it, vi } from "vitest";

import { extractContent } from "../../scraper/extract.js";
import { runFetchOrchestrator } from "../../scraper/orchestrator.js";
import { runHttpWorker } from "../../scraper/http-worker.js";
import { evaluateRobots } from "../../scraper/robots.js";

const allowedRobotsResult = {
  state: "ALLOWED" as const,
  canFetch: true,
  targetUrl: "",
  robotsUrl: "",
  userAgent: "web-agent-bot",
  crawlDelaySeconds: null,
  reason: "allowed" as const,
};

describe("fetch task 1 primitives", () => {
  it("blocks disallowed targets before content fetch runs", async () => {
    const robotsRequest = vi.fn(async () => ({
      statusCode: 200,
      headers: {},
      body: {
        text: async () => "User-agent: *\nDisallow: /private",
      },
    }));
    const contentRequest = vi.fn();

    const policy = await evaluateRobots("https://example.com/private", {
      requestFn: robotsRequest as never,
      userAgent: "web-agent-bot",
    });

    expect(policy).toEqual({
      state: "DISALLOWED",
      canFetch: false,
      targetUrl: "https://example.com/private",
      robotsUrl: "https://example.com/robots.txt",
      userAgent: "web-agent-bot",
      crawlDelaySeconds: null,
      reason: "disallowed",
    });
    expect(robotsRequest).toHaveBeenCalledTimes(1);
    expect(contentRequest).not.toHaveBeenCalled();
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
      errorClass: "NonRetryableHttpStatusError",
    });
    expect(result.meta).toMatchObject({
      attempts: 1,
      retries: 0,
    });
    expect(requestFn).toHaveBeenCalledTimes(1);
  });

  it("extracts normalized text and markdown from successful HTML fetches", async () => {
    const response = await runFetchOrchestrator("https://example.com/article", {
      evaluateRobotsFn: vi.fn(async () => ({
        ...allowedRobotsResult,
        canFetch: true,
        targetUrl: "https://example.com/article",
        robotsUrl: "https://example.com/robots.txt",
      })),
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
      metadata: {
        finalUrl: "https://example.com/article",
        contentType: "text/html; charset=utf-8",
        statusCode: 200,
      },
      fallbackReason: null,
    });
    expect(response.text).toContain("Example Article");
    expect(response.markdown).toContain("Example Article");
  });

  it("returns an explicit network fallback reason when HTTP retrieval fails", async () => {
    const evaluateRobotsFn = vi.fn(async () => ({
      ...allowedRobotsResult,
      targetUrl: "https://example.com/article",
      robotsUrl: "https://example.com/robots.txt",
    }));
    const runHttpWorkerFn = vi.fn(async () => ({
      state: "NETWORK_ERROR" as const,
      url: "https://example.com/article",
      finalUrl: null,
      statusCode: null,
      contentType: null,
      body: null,
      errorClass: "Error",
      meta: {
        attempts: 3,
        retries: 2,
        durationMs: 12,
      },
    }));

    const response = await runFetchOrchestrator("https://example.com/article", {
      evaluateRobotsFn,
      runHttpWorkerFn,
    });

    expect(response).toEqual({
      url: "https://example.com/article",
      text: "",
      markdown: "",
      metadata: {
        finalUrl: "https://example.com/article",
        contentType: null,
        statusCode: null,
      },
      fallbackReason: "network-error",
    });
    expect(evaluateRobotsFn).toHaveBeenCalledBefore(runHttpWorkerFn);
  });

  it("returns low-content-quality when extraction output is too thin", async () => {
    const response = await runFetchOrchestrator("https://example.com/thin", {
      evaluateRobotsFn: vi.fn(async () => ({
        ...allowedRobotsResult,
        targetUrl: "https://example.com/thin",
        robotsUrl: "https://example.com/robots.txt",
      })),
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
      metadata: {
        finalUrl: "https://example.com/thin",
        contentType: "text/html",
        statusCode: 200,
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
