import { beforeEach, describe, expect, it, vi } from "vitest";

const requestMock = vi.fn();

vi.mock("undici", () => ({
  request: requestMock,
}));

describe("search reliability", () => {
  beforeEach(() => {
    requestMock.mockReset();
    vi.resetModules();
    process.env.SERPER_API_KEY = "test-key";
  });

  it("retries transient 5xx failures through the shared reliability pipeline until success", async () => {
    const { search } = await import("../../sdk/index.js");

    requestMock
      .mockResolvedValueOnce(createResponse(503, { organic: [] }))
      .mockResolvedValueOnce(createResponse(502, { organic: [] }))
      .mockResolvedValueOnce(
        createResponse(200, {
          organic: [{ title: "Recovered", link: "https://example.com/recovered" }],
        }),
      );

    await expect(search("agents")).resolves.toMatchObject({
      query: "agents",
      results: [
        {
          title: "Recovered",
          url: "https://example.com/recovered",
          rank: {
            position: 1,
            providerPosition: 1,
          },
        },
      ],
      meta: {
        operation: "search",
        attempts: 3,
        retries: 2,
        cacheHit: false,
      },
      metadata: {
        resultCount: 1,
      },
    });

    expect(requestMock).toHaveBeenCalledTimes(3);
  });

  it("retries 429 responses deterministically and honors typed success metadata after recovery", async () => {
    const { search } = await import("../../sdk/index.js");

    requestMock
      .mockResolvedValueOnce(createResponse(429, { organic: [] }, { "retry-after": "0" }))
      .mockResolvedValueOnce(
        createResponse(200, {
          organic: [{ title: "Allowed", link: "https://example.com/allowed" }],
        }),
      );

    await expect(search("agents")).resolves.toMatchObject({
      query: "agents",
      results: [
        {
          title: "Allowed",
          url: "https://example.com/allowed",
          rank: {
            position: 1,
            providerPosition: 1,
          },
        },
      ],
      meta: {
        operation: "search",
        attempts: 2,
        retries: 1,
        cacheHit: false,
      },
    });

    expect(requestMock).toHaveBeenCalledTimes(2);
  });

  it("returns a stable typed invalid_request error for non-retryable provider failures", async () => {
    const { search } = await import("../../sdk/index.js");

    requestMock.mockResolvedValueOnce(createResponse(400, { message: "bad request" }));

    await expect(search("agents")).rejects.toMatchObject({
      name: "SdkError",
      kind: "invalid_request",
      retryable: false,
      statusCode: 400,
      attemptNumber: 1,
    });

    expect(requestMock).toHaveBeenCalledTimes(1);
  });

  it("keeps terminal retryable failures typed after retries are exhausted", async () => {
    const { search } = await import("../../sdk/index.js");

    requestMock
      .mockResolvedValueOnce(createResponse(503, { organic: [] }))
      .mockResolvedValueOnce(createResponse(503, { organic: [] }))
      .mockResolvedValueOnce(createResponse(503, { organic: [] }));

    await expect(search("agents")).rejects.toMatchObject({
      name: "SdkError",
      kind: "provider_unavailable",
      retryable: true,
      statusCode: 503,
      attemptNumber: 3,
    });

    expect(requestMock).toHaveBeenCalledTimes(3);
  });
});

function createResponse(
  statusCode: number,
  payload: unknown,
  headers?: Record<string, string>,
) {
  return {
    statusCode,
    headers,
    body: {
      json: vi.fn().mockResolvedValue(payload),
    },
  };
}
