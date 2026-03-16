import { describe, expect, it, vi } from "vitest";

import { runHttpWorker } from "../../scraper/http-worker.js";
import { evaluateRobots } from "../../scraper/robots.js";

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
});
