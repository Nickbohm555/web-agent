import type { AddressInfo } from "node:net";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createFetchSafetyError } from "../../core/errors/fetch-safety-error.js";
import { createSdkError } from "../../core/errors/sdk-error.js";
import {
  createEmptyFetchDecisionMetadata,
  type ComplianceDecision,
} from "../../sdk/contracts/safety.js";

const searchMock = vi.fn();
const fetchMock = vi.fn();

vi.mock("../../sdk/search.js", () => ({
  search: searchMock,
}));

vi.mock("../../sdk/fetch.js", () => ({
  fetch: fetchMock,
}));

describe("frontend API route contracts", () => {
  beforeEach(() => {
    searchMock.mockReset();
    fetchMock.mockReset();
    vi.resetModules();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns a validated success envelope for search requests", async () => {
    const { SearchApiEnvelopeSchema } = await import("../../frontend/contracts.js");

    searchMock.mockResolvedValueOnce(createSearchResponse());

    const response = await callRoute("/api/search", {
      query: "agents",
      options: {
        maxResults: 2,
        timeoutMs: 1_500,
        country: "us",
        language: "EN",
        freshness: "week",
        includeDomains: ["Docs.Example.com"],
        excludeDomains: ["blocked.com"],
      },
    });

    expect(response.status).toBe(200);

    const envelope = SearchApiEnvelopeSchema.parse(response.json);
    expect(envelope).toEqual({
      ok: true,
      operation: "search",
      durationMs: expect.any(Number),
      request: {
        query: "agents",
        options: {
          maxResults: 2,
          timeoutMs: 1_500,
          country: "US",
          language: "en",
          freshness: "week",
          domainScope: {
            includeDomains: ["example.com"],
            excludeDomains: ["blocked.com"],
          },
        },
      },
      data: createSearchResponse(),
    });
    expect(envelope.durationMs).toBeGreaterThanOrEqual(0);
    expect(searchMock).toHaveBeenCalledWith("agents", {
      maxResults: 2,
      timeoutMs: 1_500,
      country: "us",
      language: "EN",
      freshness: "week",
      includeDomains: ["Docs.Example.com"],
      excludeDomains: ["blocked.com"],
    });
  });

  it("returns a 400 validation envelope for malformed search requests", async () => {
    const { SearchApiEnvelopeSchema } = await import("../../frontend/contracts.js");

    const response = await callRoute("/api/search", {
      query: "",
      options: {
        maxResults: 0,
      },
    });

    expect(response.status).toBe(400);

    const envelope = SearchApiEnvelopeSchema.parse(response.json);
    expect(envelope.ok).toBe(false);
    expect(envelope.operation).toBe("search");
    expect(envelope.request).toBeNull();
    if (envelope.ok) {
      throw new Error("Expected search validation failure envelope.");
    }
    expect(envelope.error.code).toBe("VALIDATION_ERROR");

    if (envelope.error.details && "fieldErrors" in envelope.error.details) {
      expect(envelope.error.details.fieldErrors.query).toBeDefined();
      expect(envelope.error.details.fieldErrors.options).toBeDefined();
    } else {
      throw new Error("Expected validation error details.");
    }

    expect(searchMock).not.toHaveBeenCalled();
  });

  it("returns a typed non-2xx envelope for search SDK failures", async () => {
    const { SearchApiEnvelopeSchema } = await import("../../frontend/contracts.js");

    searchMock.mockRejectedValueOnce(
      createSdkError({
        kind: "rate_limited",
        message: "Serper rate limit",
        statusCode: 429,
        retryAfterMs: 2_000,
      }),
    );

    const response = await callRoute("/api/search", {
      query: "agents",
    });

    expect(response.status).toBe(429);

    const envelope = SearchApiEnvelopeSchema.parse(response.json);
    expect(envelope.ok).toBe(false);
    expect(envelope.operation).toBe("search");
    expect(envelope.durationMs).toBeGreaterThanOrEqual(0);
    if (envelope.ok) {
      throw new Error("Expected search SDK failure envelope.");
    }
    expect(envelope.request).toEqual({
      query: "agents",
      options: {
        maxResults: 10,
        timeoutMs: 5_000,
        country: "US",
        language: "en",
        freshness: "any",
        domainScope: {
          includeDomains: [],
          excludeDomains: [],
        },
      },
    });
    expect(envelope.error).toEqual({
      code: "RATE_LIMITED",
      message: "Serper rate limit",
      details: {
        kind: "rate_limited",
        retryable: true,
        statusCode: 429,
        retryAfterMs: 2_000,
      },
    });
  });

  it("returns a validated success envelope for fetch requests", async () => {
    const { FetchApiEnvelopeSchema } = await import("../../frontend/contracts.js");

    fetchMock.mockResolvedValueOnce(createFetchResponse());

    const response = await callRoute("/api/fetch", {
      url: "https://example.com/article#intro",
      options: {
        timeoutMs: 2_500,
        maxAgeMs: 60_000,
        fresh: true,
      },
    });

    expect(response.status).toBe(200);

    const envelope = FetchApiEnvelopeSchema.parse(response.json);
    expect(envelope).toEqual({
      ok: true,
      operation: "fetch",
      durationMs: expect.any(Number),
      request: {
        url: "https://example.com/article",
        options: {
          timeoutMs: 2_500,
          maxAgeMs: 60_000,
          fresh: true,
        },
      },
      data: createFetchResponse(),
    });
    expect(fetchMock).toHaveBeenCalledWith("https://example.com/article", {
      timeoutMs: 2_500,
      maxAgeMs: 60_000,
      fresh: true,
    });
  });

  it("returns a 400 validation envelope for malformed fetch requests", async () => {
    const { FetchApiEnvelopeSchema } = await import("../../frontend/contracts.js");

    const response = await callRoute("/api/fetch", {
      url: "not-a-url",
      options: {
        timeoutMs: -1,
      },
    });

    expect(response.status).toBe(400);

    const envelope = FetchApiEnvelopeSchema.parse(response.json);
    expect(envelope.ok).toBe(false);
    expect(envelope.operation).toBe("fetch");
    expect(envelope.request).toBeNull();
    if (envelope.ok) {
      throw new Error("Expected fetch validation failure envelope.");
    }
    expect(envelope.error.code).toBe("VALIDATION_ERROR");

    if (envelope.error.details && "fieldErrors" in envelope.error.details) {
      expect(envelope.error.details.fieldErrors.url).toBeDefined();
      expect(envelope.error.details.fieldErrors.options).toBeDefined();
    } else {
      throw new Error("Expected validation error details.");
    }

    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("keeps fetch safety and compliance failures visible to the frontend caller", async () => {
    const { FetchApiEnvelopeSchema } = await import("../../frontend/contracts.js");

    fetchMock.mockRejectedValueOnce(
      createFetchSafetyError({
        decision: createRobotsDeniedDecision(),
        fallbackReason: "browser-required",
        startedAt: 10,
        timings: {
          robotsMs: 3,
        },
      }),
    );

    const response = await callRoute("/api/fetch", {
      url: "https://example.com/private",
    });

    expect(response.status).toBe(403);

    const envelope = FetchApiEnvelopeSchema.parse(response.json);
    expect(envelope.ok).toBe(false);
    expect(envelope.operation).toBe("fetch");
    expect(envelope.durationMs).toBeGreaterThanOrEqual(0);
    if (envelope.ok) {
      throw new Error("Expected fetch policy failure envelope.");
    }
    expect(envelope.request).toEqual({
      url: "https://example.com/private",
      options: {
        timeoutMs: 5_000,
        maxAgeMs: 300_000,
        fresh: false,
      },
    });
    expect(envelope.error.code).toBe("POLICY_DENIED");
    expect(envelope.error.message).toBe("Request was denied by policy.");

    if (envelope.error.details && "kind" in envelope.error.details) {
      expect(envelope.error.details).toMatchObject({
        kind: "policy_denied",
        retryable: false,
        stage: "robots",
        reason: "ROBOTS_DENY",
        fallbackReason: "browser-required",
        meta: {
          operation: "fetch",
          attempts: 1,
          retries: 0,
          cacheHit: false,
        },
        metadata: {
          finalUrl: "https://example.com/private",
          contentType: null,
          statusCode: null,
          decisions: {
            safety: null,
            compliance: {
              stage: "robots",
              outcome: "deny",
              reason: "ROBOTS_DENY",
              target: {
                url: "https://example.com/private",
                scheme: "https",
                hostname: "example.com",
                port: null,
              },
            },
          },
        },
      });
    } else {
      throw new Error("Expected SDK error details.");
    }
  });
});

async function callRoute(
  route: "/api/search" | "/api/fetch",
  payload: unknown,
): Promise<{ status: number; json: unknown }> {
  const { createFrontendServerApp } = await import("../../frontend/server.js");
  const app = createFrontendServerApp();
  const server = await new Promise<import("node:http").Server>((resolve) => {
    const listeningServer = app.listen(0, "127.0.0.1", () => {
      resolve(listeningServer);
    });
  });

  const address = server.address() as AddressInfo;

  try {
    const response = await fetch(`http://127.0.0.1:${address.port}${route}`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    return {
      status: response.status,
      json: await response.json(),
    };
  } finally {
    await new Promise<void>((resolve, reject) => {
      server.close((error) => {
        if (error) {
          reject(error);
          return;
        }

        resolve();
      });
    });
  }
}

function createSearchResponse() {
  return {
    query: "agents",
    results: [
      {
        title: "Example",
        url: "https://example.com/docs",
        snippet: "Useful docs",
        rank: {
          position: 1,
          providerPosition: 3,
        },
      },
    ],
    meta: {
      operation: "search",
      durationMs: 12,
      attempts: 1,
      retries: 0,
      cacheHit: false,
      timings: {
        providerMs: 8,
        mappingMs: 2,
      },
      usage: {
        provider: {
          organicResults: 1,
        },
      },
    },
    metadata: {
      resultCount: 1,
    },
  };
}

function createFetchResponse() {
  return {
    url: "https://example.com/article",
    text: "Article body",
    markdown: "# Article body",
    meta: {
      operation: "fetch",
      durationMs: 14,
      attempts: 1,
      retries: 0,
      cacheHit: false,
      timings: {
        networkMs: 10,
      },
    },
    metadata: {
      finalUrl: "https://example.com/article",
      contentType: "text/html; charset=utf-8",
      statusCode: 200,
      decisions: createEmptyFetchDecisionMetadata(),
    },
    fallbackReason: null,
  };
}

function createRobotsDeniedDecision(): Extract<ComplianceDecision, { outcome: "deny" }> {
  return {
    stage: "robots",
    outcome: "deny",
    reason: "ROBOTS_DENY",
    target: {
      url: "https://example.com/private",
      scheme: "https",
      hostname: "example.com",
      port: null,
    },
  };
}
