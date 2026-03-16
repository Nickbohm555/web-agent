import { beforeEach, describe, expect, it, vi } from "vitest";

const requestMock = vi.fn();

vi.mock("undici", () => ({
  request: requestMock,
}));

describe("Serper transport", () => {
  beforeEach(() => {
    requestMock.mockReset();
    vi.resetModules();
  });

  it("retries 429 and succeeds with validated provider payload", async () => {
    const { callSerperSearch } = await import("../../providers/serper/client.js");

    requestMock
      .mockResolvedValueOnce(createResponse(429, { message: "rate limited" }))
      .mockResolvedValueOnce(createResponse(200, { organic: [{ title: "Result", link: "https://example.com" }] }));

    await expect(
      callSerperSearch("test query", { limit: 5 }, { apiKey: "test-key" }),
    ).resolves.toMatchObject({
      payload: {
        organic: [{ title: "Result", link: "https://example.com" }],
      },
      meta: {
        attempts: 2,
        retries: 1,
      },
    });

    expect(requestMock).toHaveBeenCalledTimes(2);
  });

  it("retries 5xx responses and transport errors within the bounded budget", async () => {
    const { callSerperSearch } = await import("../../providers/serper/client.js");

    requestMock
      .mockRejectedValueOnce(createTransportError("ETIMEDOUT"))
      .mockResolvedValueOnce(createResponse(503, { message: "unavailable" }))
      .mockResolvedValueOnce(createResponse(200, { organic: [] }));

    await expect(
      callSerperSearch("test query", undefined, { apiKey: "test-key" }),
    ).resolves.toMatchObject({
      payload: {
        organic: [],
      },
      meta: {
        attempts: 3,
        retries: 2,
      },
    });

    expect(requestMock).toHaveBeenCalledTimes(3);
  });

  it("aborts immediately on non-retryable 4xx responses", async () => {
    const { callSerperSearch } = await import("../../providers/serper/client.js");

    requestMock.mockResolvedValueOnce(createResponse(400, { message: "bad request" }));

    await expect(
      callSerperSearch("test query", undefined, { apiKey: "test-key" }),
    ).rejects.toMatchObject({
      name: "SdkError",
      kind: "invalid_request",
      retryable: false,
      statusCode: 400,
      attemptNumber: 1,
    });

    expect(requestMock).toHaveBeenCalledTimes(1);
  });

  it("rejects malformed provider payloads without retrying", async () => {
    const { callSerperSearch } = await import("../../providers/serper/client.js");

    requestMock.mockResolvedValueOnce(createResponse(200, { organic: "invalid" }));

    await expect(
      callSerperSearch("test query", undefined, { apiKey: "test-key" }),
    ).rejects.toThrow();

    expect(requestMock).toHaveBeenCalledTimes(1);
  });
});

describe("sdk search", () => {
  beforeEach(() => {
    requestMock.mockReset();
    vi.resetModules();
    process.env.SERPER_API_KEY = "test-key";
  });

  it("returns normalized search results without leaking provider fields", async () => {
    const { search } = await import("../../sdk/index.js");

    requestMock.mockResolvedValueOnce(
      createResponse(200, {
        organic: [
          {
            title: "  Example Domain  ",
            link: "https://example.com",
            snippet: "  Example snippet  ",
            position: 7,
            sitelinks: [{ title: "Ignored child" }],
          },
          {
            title: "Second Result",
            link: "https://example.org/docs",
          },
        ],
        credits: 1,
      }),
    );

    await expect(
      search("  Example Query  ", {
        limit: 5,
        country: "us",
        language: "EN",
      }),
    ).resolves.toEqual({
      query: "Example Query",
      results: [
        {
          title: "Example Domain",
          url: "https://example.com/",
          snippet: "Example snippet",
          rank: {
            position: 1,
            providerPosition: 7,
          },
        },
        {
          title: "Second Result",
          url: "https://example.org/docs",
          snippet: "",
          rank: {
            position: 2,
            providerPosition: 2,
          },
        },
      ],
      meta: {
        operation: "search",
        durationMs: expect.any(Number),
        attempts: 1,
        retries: 0,
        cacheHit: false,
        timings: {
          providerMs: expect.any(Number),
          mappingMs: expect.any(Number),
        },
        usage: {
          provider: {
            organicResults: 2,
          },
        },
      },
      metadata: {
        resultCount: 2,
      },
    });

    expect(requestMock).toHaveBeenCalledTimes(1);
    expect(requestMock).toHaveBeenCalledWith(
      "https://google.serper.dev/search",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          "content-type": "application/json",
          "x-api-key": "test-key",
        }),
        body: JSON.stringify({
          q: "Example Query",
          num: 5,
          gl: "us",
          hl: "en",
        }),
      }),
    );
  });

  it("produces identical normalized output for equivalent input and option shapes", async () => {
    const { search } = await import("../../sdk/index.js");

    requestMock.mockResolvedValue(createResponse(200, {
      organic: [
        {
          title: "Result",
          link: "https://example.com/path",
          snippet: "Snippet",
          position: 3,
        },
      ],
    }));

    const first = await search(" Example Query ", {
      limit: 1,
      country: "us",
      language: "EN",
    });
    const second = await search("Example Query", {
      limit: 1,
      country: "US",
      language: "en",
    });

    expect(first).toMatchObject({
      query: "Example Query",
      results: [
        {
          title: "Result",
          url: "https://example.com/path",
          snippet: "Snippet",
          rank: {
            position: 1,
            providerPosition: 3,
          },
        },
      ],
      metadata: {
        resultCount: 1,
      },
    });
    expect(first.meta).toMatchObject({
      operation: "search",
      attempts: 1,
      retries: 0,
      cacheHit: false,
      timings: {
        providerMs: expect.any(Number),
        mappingMs: expect.any(Number),
      },
    });
    expect(second).toMatchObject({
      query: "Example Query",
      results: first.results,
      metadata: {
        resultCount: 1,
      },
    });
    expect(second.meta).toMatchObject({
      operation: "search",
      attempts: 1,
      retries: 0,
      cacheHit: false,
      timings: {
        providerMs: expect.any(Number),
        mappingMs: expect.any(Number),
      },
    });
    expect(requestMock).toHaveBeenCalledTimes(2);
  });
});

function createResponse(statusCode: number, payload: unknown) {
  return {
    statusCode,
    body: {
      json: vi.fn().mockResolvedValue(payload),
    },
  };
}

function createTransportError(code: string) {
  const error = new Error(`transport error ${code}`) as Error & { code: string };
  error.code = code;
  return error;
}
