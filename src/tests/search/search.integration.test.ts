import { beforeEach, describe, expect, it, vi } from "vitest";

const requestMock = vi.fn();

vi.mock("undici", () => ({
  request: requestMock,
}));

describe("Serper transport", () => {
  beforeEach(() => {
    requestMock.mockReset();
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
    ).rejects.toThrow("Non-retryable Serper status 400");

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
