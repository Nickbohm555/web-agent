import { beforeEach, describe, expect, it, vi } from "vitest";

import type { FetchResponse } from "../../sdk/contracts/fetch.js";

const runFetchOrchestratorMock = vi.fn<
  (url: string, options?: { http?: { timeoutMs?: number } }) => Promise<FetchResponse>
>();

vi.mock("../../scraper/orchestrator.js", () => ({
  runFetchOrchestrator: runFetchOrchestratorMock,
}));

describe("fetch metadata", () => {
  beforeEach(() => {
    runFetchOrchestratorMock.mockReset();
    vi.resetModules();
  });

  it("emits stable inspectable call metadata on successful fetch responses", async () => {
    const { fetch } = await import("../../sdk/index.js");

    runFetchOrchestratorMock.mockResolvedValueOnce(
      createFetchResponse("https://example.com/article", {
        text: "Deterministic article body",
        markdown: "# Deterministic article body",
        timings: {
          robotsMs: 1,
          httpMs: 12,
          extractionMs: 3,
        },
      }),
    );

    const response = await fetch("https://example.com/article");

    expect(response).toMatchObject({
      url: "https://example.com/article",
      text: "Deterministic article body",
      markdown: "# Deterministic article body",
      meta: {
        operation: "fetch",
        attempts: 1,
        retries: 0,
        cacheHit: false,
        usage: {
          content: {
            textChars: 26,
            markdownChars: 28,
          },
        },
      },
      metadata: {
        finalUrl: "https://example.com/article",
        contentType: "text/html; charset=utf-8",
        statusCode: 200,
      },
      fallbackReason: null,
    });

    expect(response.meta.durationMs).toBeGreaterThanOrEqual(0);
    expect(response.meta.timings.cacheReadMs).toBeGreaterThanOrEqual(0);
    expect(response.meta.timings.networkMs).toBeGreaterThanOrEqual(0);
    expect(response.meta.timings.robotsMs).toBeGreaterThanOrEqual(0);
    expect(response.meta.timings.httpMs).toBeGreaterThanOrEqual(0);
    expect(response.meta.timings.extractionMs).toBeGreaterThanOrEqual(0);
  });

  it("preserves typed fetch failures with stable fetch-specific context", async () => {
    const { fetch } = await import("../../sdk/index.js");

    const error = Object.assign(new Error("network"), {
      name: "SdkError",
      kind: "network",
      retryable: true,
      attemptNumber: 2,
      operation: "fetch",
      fallbackReason: "network-error",
      meta: {
        operation: "fetch",
        durationMs: 8,
        attempts: 2,
        retries: 1,
        cacheHit: false,
        timings: {
          robotsMs: 1,
          httpMs: 7,
        },
      },
      metadata: {
        finalUrl: "https://example.com/article",
        contentType: null,
        statusCode: null,
      },
    });

    runFetchOrchestratorMock.mockRejectedValueOnce(error);

    await expect(fetch("https://example.com/article")).rejects.toMatchObject({
      name: "SdkError",
      kind: "network",
      retryable: true,
      attemptNumber: 2,
      operation: "fetch",
      fallbackReason: "network-error",
      meta: {
        operation: "fetch",
        attempts: 2,
        retries: 1,
        cacheHit: false,
        timings: {
          robotsMs: 1,
          httpMs: 7,
        },
      },
      metadata: {
        finalUrl: "https://example.com/article",
        contentType: null,
        statusCode: null,
      },
    });
  });
});

function createFetchResponse(
  url: string,
  input: {
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
      durationMs: 16,
      attempts: 1,
      retries: 0,
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
    },
    fallbackReason: null,
  };
}
