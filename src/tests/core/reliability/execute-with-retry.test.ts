import { describe, expect, it, vi } from "vitest";
import { z } from "zod";

import { mapError } from "../../../core/errors/map-error.js";
import { createSdkError } from "../../../core/errors/sdk-error.js";
import { executeWithRetry } from "../../../core/reliability/execute-with-retry.js";
import { parseRetryAfter } from "../../../core/reliability/retry-after.js";

describe("mapError", () => {
  it("maps 429 responses to rate_limited with retry metadata", () => {
    const mapped = mapError({
      statusCode: 429,
      retryAfter: "2",
    });

    expect(mapped).toMatchObject({
      name: "SdkError",
      kind: "rate_limited",
      retryable: true,
      statusCode: 429,
      retryAfterMs: 2_000,
      message: "Request was rate limited.",
    });
  });

  it("maps timeout transport codes to timeout", () => {
    const mapped = mapError({
      code: "UND_ERR_CONNECT_TIMEOUT",
    });

    expect(mapped).toMatchObject({
      kind: "timeout",
      retryable: true,
      message: "Request timed out.",
    });
  });

  it("maps network transport codes to network", () => {
    const mapped = mapError({
      code: "ECONNRESET",
    });

    expect(mapped).toMatchObject({
      kind: "network",
      retryable: true,
      message: "Network request failed.",
    });
  });

  it("maps retryable provider statuses to provider_unavailable", () => {
    const mapped = mapError({
      statusCode: 503,
    });

    expect(mapped).toMatchObject({
      kind: "provider_unavailable",
      retryable: true,
      statusCode: 503,
      message: "Provider is temporarily unavailable.",
    });
  });

  it("maps schema failures to invalid_request", () => {
    const parsed = z.string().safeParse(42);

    if (parsed.success) {
      throw new Error("Expected schema parse to fail.");
    }

    const mapped = mapError(parsed.error);

    expect(mapped).toMatchObject({
      kind: "invalid_request",
      retryable: false,
      message: "Request is invalid.",
    });
  });

  it("maps explicit policy error codes to policy_denied", () => {
    const mapped = mapError({
      code: "ROBOTS_DENIED",
      statusCode: 403,
    });

    expect(mapped).toMatchObject({
      kind: "policy_denied",
      retryable: false,
      statusCode: 403,
      message: "Request was denied by policy.",
    });
  });

  it("maps unavailable content codes to content_unavailable", () => {
    const mapped = mapError({
      code: "UNSUPPORTED_CONTENT_TYPE",
      statusCode: 415,
    });

    expect(mapped).toMatchObject({
      kind: "content_unavailable",
      retryable: false,
      statusCode: 415,
      message: "Requested content is unavailable.",
    });
  });

  it("preserves existing sdk errors", () => {
    const existing = createSdkError({
      kind: "policy_denied",
      statusCode: 403,
    });

    expect(mapError(existing)).toBe(existing);
  });

  it("falls back to unknown when no stable classifier matches", () => {
    const mapped = mapError(new Error("opaque failure"));

    expect(mapped).toMatchObject({
      kind: "unknown",
      retryable: false,
      message: "Unexpected SDK error.",
    });
  });

  it("parses HTTP-date retry-after values", () => {
    const mapped = mapError({
      statusCode: 429,
      retryAfter: "Wed, 21 Oct 2015 07:28:00 GMT",
    });

    expect(mapped).toMatchObject({
      kind: "rate_limited",
      retryAfterMs: 0,
    });
  });
});

describe("parseRetryAfter", () => {
  it("parses delay-seconds values", () => {
    expect(parseRetryAfter("1.5")).toBe(1_500);
  });

  it("parses HTTP-date values relative to now", () => {
    expect(parseRetryAfter("Wed, 21 Oct 2015 07:28:00 GMT", Date.parse("Wed, 21 Oct 2015 07:27:58 GMT"))).toBe(2_000);
  });

  it("returns undefined for invalid values", () => {
    expect(parseRetryAfter("not-a-date")).toBeUndefined();
  });
});

describe("executeWithRetry", () => {
  it("retries deterministically until success", async () => {
    const sleep = vi.fn(async () => {});
    const operation = vi
      .fn<({ attemptNumber }: { attemptNumber: number }) => Promise<string>>()
      .mockImplementation(async ({ attemptNumber }) => {
        if (attemptNumber < 3) {
          throw {
            statusCode: 503,
          };
        }

        return "ok";
      });

    const result = await executeWithRetry(
      ({ attemptNumber, retriesConsumed }) => operation({ attemptNumber, retriesConsumed } as never),
      {
        retries: 3,
        minTimeoutMs: 100,
        maxTimeoutMs: 500,
        sleep,
      },
    );

    expect(result).toEqual({
      value: "ok",
      attempts: 3,
      retries: 2,
    });
    expect(operation).toHaveBeenCalledTimes(3);
    expect(sleep).toHaveBeenNthCalledWith(1, 100);
    expect(sleep).toHaveBeenNthCalledWith(2, 200);
  });

  it("uses retry-after before fallback backoff", async () => {
    const sleep = vi.fn(async () => {});
    const operation = vi
      .fn<() => Promise<string>>()
      .mockRejectedValueOnce({
        statusCode: 429,
        retryAfter: "2",
      })
      .mockResolvedValueOnce("ok");

    const result = await executeWithRetry(
      async () => operation(),
      {
        retries: 2,
        minTimeoutMs: 100,
        maxTimeoutMs: 500,
        sleep,
      },
    );

    expect(result).toEqual({
      value: "ok",
      attempts: 2,
      retries: 1,
    });
    expect(sleep).toHaveBeenCalledTimes(1);
    expect(sleep).toHaveBeenCalledWith(2_000);
  });

  it("short-circuits non-retryable failures", async () => {
    const sleep = vi.fn(async () => {});

    await expect(
      executeWithRetry(
        async () => {
          throw {
            statusCode: 400,
          };
        },
        {
          retries: 3,
          sleep,
        },
      ),
    ).rejects.toMatchObject({
      kind: "invalid_request",
      retryable: false,
      statusCode: 400,
      attemptNumber: 1,
    });

    expect(sleep).not.toHaveBeenCalled();
  });

  it("returns the final mapped error when the retry budget is exhausted", async () => {
    const sleep = vi.fn(async () => {});

    await expect(
      executeWithRetry(
        async () => {
          throw {
            statusCode: 503,
          };
        },
        {
          retries: 2,
          minTimeoutMs: 25,
          maxTimeoutMs: 100,
          sleep,
        },
      ),
    ).rejects.toMatchObject({
      kind: "provider_unavailable",
      retryable: true,
      statusCode: 503,
      attemptNumber: 3,
    });

    expect(sleep).toHaveBeenCalledTimes(2);
    expect(sleep).toHaveBeenNthCalledWith(1, 25);
    expect(sleep).toHaveBeenNthCalledWith(2, 50);
  });
});
