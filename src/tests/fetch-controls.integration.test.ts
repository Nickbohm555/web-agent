import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { FetchResponse } from "../sdk/contracts/fetch.js";

const runFetchOrchestratorMock = vi.fn<
  (url: string, options?: { http?: { timeoutMs?: number } }) => Promise<FetchResponse>
>();

vi.mock("../scraper/orchestrator.js", () => ({
  runFetchOrchestrator: runFetchOrchestratorMock,
}));

describe("fetch controls integration", () => {
  beforeEach(() => {
    runFetchOrchestratorMock.mockReset();
    vi.resetModules();
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-03-15T12:00:00.000Z"));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("misses on the first call and serves a hit for a repeated equivalent call within maxAge", async () => {
    const { fetch: sdkFetch } = await import("../sdk/index.js");

    runFetchOrchestratorMock.mockResolvedValueOnce(
      createFetchResponse("https://example.com/article", "cached article"),
    );

    const first = await sdkFetch("https://example.com/article#intro", {
      maxAgeMs: 1_000,
    });

    vi.setSystemTime(new Date("2026-03-15T12:00:00.500Z"));

    const second = await sdkFetch("https://example.com/article", {
      maxAgeMs: 1_000,
    });

    expect(first).toMatchObject({
      url: "https://example.com/article",
      text: "cached article",
      markdown: "cached article",
      metadata: {
        finalUrl: "https://example.com/article",
        contentType: "text/html; charset=utf-8",
        statusCode: 200,
      },
      fallbackReason: null,
    });
    expect(first.meta).toMatchObject({
      operation: "fetch",
      attempts: 1,
      retries: 0,
      cacheHit: false,
    });
    expect(second).toMatchObject({
      url: "https://example.com/article",
      text: "cached article",
      markdown: "cached article",
      metadata: {
        finalUrl: "https://example.com/article",
        contentType: "text/html; charset=utf-8",
        statusCode: 200,
      },
      fallbackReason: null,
    });
    expect(second.meta).toMatchObject({
      operation: "fetch",
      attempts: 1,
      retries: 0,
      cacheHit: true,
    });
    expect(runFetchOrchestratorMock).toHaveBeenCalledTimes(1);
    expect(runFetchOrchestratorMock).toHaveBeenCalledWith(
      "https://example.com/article",
      {
        http: {
          timeoutMs: 5_000,
        },
      },
    );
  });

  it("treats entries older than maxAge as stale and refreshes them", async () => {
    const { fetch: sdkFetch } = await import("../sdk/index.js");

    runFetchOrchestratorMock
      .mockResolvedValueOnce(
        createFetchResponse("https://example.com/article", "old article"),
      )
      .mockResolvedValueOnce(
        createFetchResponse("https://example.com/article", "refreshed article"),
      );

    const first = await sdkFetch("https://example.com/article", {
      maxAgeMs: 1_000,
    });

    vi.setSystemTime(new Date("2026-03-15T12:00:01.500Z"));

    const second = await sdkFetch("https://example.com/article", {
      maxAgeMs: 1_000,
    });

    expect(first.text).toBe("old article");
    expect(second.text).toBe("refreshed article");
    expect(runFetchOrchestratorMock).toHaveBeenCalledTimes(2);
  });

  it("bypasses cache reads for fresh requests and updates the cache for later non-fresh calls", async () => {
    const { fetch: sdkFetch } = await import("../sdk/index.js");

    runFetchOrchestratorMock
      .mockResolvedValueOnce(
        createFetchResponse("https://example.com/article", "initial article"),
      )
      .mockResolvedValueOnce(
        createFetchResponse("https://example.com/article", "fresh article"),
      );

    const initial = await sdkFetch("https://example.com/article", {
      maxAgeMs: 5_000,
    });

    vi.setSystemTime(new Date("2026-03-15T12:00:00.100Z"));

    const fresh = await sdkFetch("https://example.com/article", {
      maxAgeMs: 5_000,
      fresh: true,
    });

    vi.setSystemTime(new Date("2026-03-15T12:00:00.200Z"));

    const cachedAfterFresh = await sdkFetch("https://example.com/article", {
      maxAgeMs: 5_000,
    });

    expect(initial.text).toBe("initial article");
    expect(fresh.text).toBe("fresh article");
    expect(fresh.meta.cacheHit).toBe(false);
    expect(cachedAfterFresh).toMatchObject({
      url: "https://example.com/article",
      text: "fresh article",
      markdown: "fresh article",
      metadata: {
        finalUrl: "https://example.com/article",
        contentType: "text/html; charset=utf-8",
        statusCode: 200,
      },
      fallbackReason: null,
    });
    expect(cachedAfterFresh.meta).toMatchObject({
      operation: "fetch",
      attempts: 1,
      retries: 0,
      cacheHit: true,
    });
    expect(runFetchOrchestratorMock).toHaveBeenCalledTimes(2);
  });
});

function createFetchResponse(url: string, text: string): FetchResponse {
  return {
    url,
    text,
    markdown: text,
    meta: {
      operation: "fetch",
      durationMs: 5,
      attempts: 1,
      retries: 0,
      cacheHit: false,
      timings: {
        networkMs: 5,
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
