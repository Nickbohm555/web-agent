import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { describe, expect, it, vi } from "vitest";

import { evaluateRobotsCompliance } from "../../scraper/robots/evaluator.js";

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
});

async function readFixture(name: string): Promise<string> {
  return readFile(new URL(name, `file://${fixturesDir}/`), "utf8");
}
