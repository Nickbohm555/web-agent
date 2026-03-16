import { beforeEach, describe, expect, it, vi } from "vitest";

import { runHttpWorker } from "../../scraper/http-worker.js";
import type { FetchResponse } from "../../sdk/contracts/fetch.js";
import { createEmptyFetchDecisionMetadata } from "../../sdk/contracts/safety.js";

const runFetchOrchestratorMock = vi.fn<
  (url: string, options?: { http?: { timeoutMs?: number } }) => Promise<FetchResponse>
>();

vi.mock("../../scraper/orchestrator.js", () => ({
  runFetchOrchestrator: runFetchOrchestratorMock,
}));

describe("fetch reliability", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    runFetchOrchestratorMock.mockReset();
    vi.resetModules();
  });

  it("retries transient transport failures through the shared executor until success", async () => {
    const sleep = vi.fn(async () => {});
    const requestFn = vi
      .fn()
      .mockRejectedValueOnce({
        code: "UND_ERR_CONNECT_TIMEOUT",
        name: "ConnectTimeoutError",
      })
      .mockRejectedValueOnce({
        code: "ECONNRESET",
        name: "SocketError",
      })
      .mockResolvedValueOnce({
        statusCode: 200,
        headers: {
          "content-type": "text/html; charset=utf-8",
        },
        body: {
          text: async () => "<html><body>ok</body></html>",
        },
      });

    const result = await runHttpWorker("https://example.com/article", {
      requestFn: requestFn as never,
      retryPolicy: {
        retries: 3,
        minTimeoutMs: 100,
        maxTimeoutMs: 500,
        sleep,
      },
    });

    expect(result).toMatchObject({
      state: "OK",
      meta: {
        attempts: 3,
        retries: 2,
      },
    });
    expect(requestFn).toHaveBeenCalledTimes(3);
    expect(sleep).toHaveBeenNthCalledWith(1, 100);
    expect(sleep).toHaveBeenNthCalledWith(2, 200);
  });

  it("honors retry-after for retryable rate limits before succeeding", async () => {
    const sleep = vi.fn(async () => {});
    const requestFn = vi
      .fn()
      .mockResolvedValueOnce({
        statusCode: 429,
        headers: {
          "retry-after": "2",
        },
        body: {
          text: async () => "",
        },
      })
      .mockResolvedValueOnce({
        statusCode: 200,
        headers: {
          "content-type": "text/html",
        },
        body: {
          text: async () => "<html><body>ok</body></html>",
        },
      });

    const result = await runHttpWorker("https://example.com/rate-limited", {
      requestFn: requestFn as never,
      retryPolicy: {
        retries: 2,
        minTimeoutMs: 100,
        maxTimeoutMs: 500,
        sleep,
      },
    });

    expect(result).toMatchObject({
      state: "OK",
      meta: {
        attempts: 2,
        retries: 1,
      },
    });
    expect(requestFn).toHaveBeenCalledTimes(2);
    expect(sleep).toHaveBeenCalledTimes(1);
    expect(sleep).toHaveBeenCalledWith(2_000);
  });

  it("returns a stable typed terminal error for non-retryable failures", async () => {
    const sleep = vi.fn(async () => {});
    const requestFn = vi.fn().mockResolvedValue({
      statusCode: 403,
      headers: {},
      body: {
        text: async () => "forbidden",
      },
    });

    const result = await runHttpWorker("https://example.com/forbidden", {
      requestFn: requestFn as never,
      retryPolicy: {
        retries: 3,
        sleep,
      },
    });

    expect(result).toMatchObject({
      state: "HTTP_STATUS_UNSUPPORTED",
      errorClass: "SdkError",
      errorKind: "invalid_request",
      retryable: false,
      statusCode: 403,
      meta: {
        attempts: 1,
        retries: 0,
      },
    });
    expect(requestFn).toHaveBeenCalledTimes(1);
    expect(sleep).not.toHaveBeenCalled();
  });

  it("surfaces transient recovery metadata deterministically at the SDK boundary", async () => {
    const { fetch } = await import("../../sdk/index.js");

    runFetchOrchestratorMock.mockResolvedValueOnce(
      createFetchResponse("https://example.com/article", {
        attempts: 3,
        retries: 2,
        fallbackReason: null,
        text: "Recovered fetch body",
        markdown: "# Recovered fetch body",
        timings: {
          robotsMs: 1,
          httpMs: 12,
          extractionMs: 4,
        },
      }),
    );

    await expect(fetch("https://example.com/article")).resolves.toMatchObject({
      url: "https://example.com/article",
      text: "Recovered fetch body",
      markdown: "# Recovered fetch body",
      fallbackReason: null,
      meta: {
        operation: "fetch",
        attempts: 3,
        retries: 2,
        cacheHit: false,
        usage: {
          content: {
            textChars: 20,
            markdownChars: 22,
          },
        },
      },
      metadata: {
        finalUrl: "https://example.com/article",
        contentType: "text/html; charset=utf-8",
        statusCode: 200,
      },
    });

    expect(runFetchOrchestratorMock).toHaveBeenCalledTimes(1);
  });

  it("preserves deterministic non-retryable fetch failures at the SDK boundary", async () => {
    const { fetch } = await import("../../sdk/index.js");

    const error = Object.assign(new Error("forbidden"), {
      name: "SdkError",
      kind: "invalid_request",
      retryable: false,
      statusCode: 403,
      attemptNumber: 1,
      operation: "fetch",
      fallbackReason: "browser-required",
      meta: {
        operation: "fetch",
        durationMs: 6,
        attempts: 1,
        retries: 0,
        cacheHit: false,
        timings: {
          robotsMs: 1,
          httpMs: 5,
        },
      },
      metadata: {
        finalUrl: "https://example.com/forbidden",
        contentType: null,
        statusCode: 403,
      },
    });

    runFetchOrchestratorMock.mockRejectedValueOnce(error);

    await expect(fetch("https://example.com/forbidden")).rejects.toMatchObject({
      name: "SdkError",
      kind: "invalid_request",
      retryable: false,
      statusCode: 403,
      attemptNumber: 1,
      operation: "fetch",
      fallbackReason: "browser-required",
      meta: {
        operation: "fetch",
        attempts: 1,
        retries: 0,
        cacheHit: false,
        timings: {
          robotsMs: 1,
          httpMs: 5,
        },
      },
      metadata: {
        finalUrl: "https://example.com/forbidden",
        contentType: null,
        statusCode: 403,
      },
    });

    expect(runFetchOrchestratorMock).toHaveBeenCalledTimes(1);
  });
});

function createFetchResponse(
  url: string,
  input: {
    attempts: number;
    retries: number;
    fallbackReason: FetchResponse["fallbackReason"];
    text: string;
    markdown: string;
    timings: Record<string, number>;
  },
): FetchResponse {
  return {
    url,
    text: input.text,
    markdown: input.markdown,
    meta: {
      operation: "fetch",
      durationMs: 18,
      attempts: input.attempts,
      retries: input.retries,
      cacheHit: false,
      timings: input.timings,
      usage: {
        content: {
          textChars: input.text.length,
          markdownChars: input.markdown.length,
        },
      },
    },
    metadata: {
      finalUrl: url,
      contentType: "text/html; charset=utf-8",
      statusCode: 200,
      decisions: createEmptyFetchDecisionMetadata(),
    },
    fallbackReason: input.fallbackReason,
  };
}
