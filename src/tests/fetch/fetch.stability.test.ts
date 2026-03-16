import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it, vi } from "vitest";

import { runFetchOrchestrator } from "../../scraper/orchestrator.js";

const articleFixture = readFileSync(
  resolve(process.cwd(), "src/tests/fixtures/fetch/article.html"),
  "utf8",
);

const allowedRobotsResult = {
  state: "ALLOWED" as const,
  canFetch: true,
  targetUrl: "",
  robotsUrl: "",
  userAgent: "web-agent-bot",
  crawlDelaySeconds: null,
  reason: "allowed" as const,
};

describe("fetch stability", () => {
  it("returns the same normalized response across repeated equivalent article runs", async () => {
    const runOnce = () =>
      runFetchOrchestrator("https://example.com/articles/deterministic", {
        evaluateRobotsFn: vi.fn(async () => ({
          ...allowedRobotsResult,
          targetUrl: "https://example.com/articles/deterministic",
          robotsUrl: "https://example.com/robots.txt",
        })),
        runHttpWorkerFn: vi.fn(async () => ({
          state: "OK" as const,
          url: "https://example.com/articles/deterministic",
          finalUrl: "https://example.com/articles/deterministic",
          statusCode: 200,
          contentType: "text/html; charset=utf-8",
          body: articleFixture,
          meta: {
            attempts: 1,
            retries: 0,
            durationMs: 4,
          },
        })),
      });

    const responses = await Promise.all(
      Array.from({ length: 5 }, () => runOnce()),
    );

    expect(responses).toHaveLength(5);
    expect(responses.every((response) => response.fallbackReason === null)).toBe(true);
    expect(responses.every((response) => response.text.length >= 120)).toBe(true);
    responses.forEach((response) => {
      expect(response).toMatchObject({
        url: "https://example.com/articles/deterministic",
        text: responses[0]?.text,
        markdown: responses[0]?.markdown,
        metadata: {
          finalUrl: "https://example.com/articles/deterministic",
          contentType: "text/html; charset=utf-8",
          statusCode: 200,
        },
        fallbackReason: null,
      });
      expect(response.meta).toMatchObject({
        operation: "fetch",
        attempts: 1,
        retries: 0,
        cacheHit: false,
        timings: {
          robotsMs: expect.any(Number),
          httpMs: expect.any(Number),
          extractionMs: expect.any(Number),
        },
      });
    });
  });

  it("keeps low-content fallback deterministic across repeated thin-content runs", async () => {
    const thinHtml = `
      <html>
        <head><title>Thin Fixture</title></head>
        <body><main><p>Too short.</p></main></body>
      </html>
    `;

    const runOnce = () =>
      runFetchOrchestrator("https://example.com/articles/thin", {
        evaluateRobotsFn: vi.fn(async () => ({
          ...allowedRobotsResult,
          targetUrl: "https://example.com/articles/thin",
          robotsUrl: "https://example.com/robots.txt",
        })),
        runHttpWorkerFn: vi.fn(async () => ({
          state: "OK" as const,
          url: "https://example.com/articles/thin",
          finalUrl: "https://example.com/articles/thin",
          statusCode: 200,
          contentType: "text/html; charset=utf-8",
          body: thinHtml,
          meta: {
            attempts: 1,
            retries: 0,
            durationMs: 2,
          },
        })),
      });

    const responses = await Promise.all(
      Array.from({ length: 5 }, () => runOnce()),
    );

    responses.forEach((response) => {
      expect(response).toMatchObject({
        url: "https://example.com/articles/thin",
        text: "Too short.",
        markdown: "Too short.",
        metadata: {
          finalUrl: "https://example.com/articles/thin",
          contentType: "text/html; charset=utf-8",
          statusCode: 200,
        },
        fallbackReason: "low-content-quality",
      });
      expect(response.meta).toMatchObject({
        operation: "fetch",
        attempts: 1,
        retries: 0,
        cacheHit: false,
        timings: {
          robotsMs: expect.any(Number),
          httpMs: expect.any(Number),
          extractionMs: expect.any(Number),
        },
      });
    });
    expect(responses[0]).toEqual({
      url: "https://example.com/articles/thin",
      text: "Too short.",
      markdown: "Too short.",
      meta: {
        operation: "fetch",
        durationMs: expect.any(Number),
        attempts: 1,
        retries: 0,
        cacheHit: false,
        timings: {
          robotsMs: expect.any(Number),
          httpMs: expect.any(Number),
          extractionMs: expect.any(Number),
        },
      },
      metadata: {
        finalUrl: "https://example.com/articles/thin",
        contentType: "text/html; charset=utf-8",
        statusCode: 200,
      },
      fallbackReason: "low-content-quality",
    });
  });
});
