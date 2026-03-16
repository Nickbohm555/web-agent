import { describe, expect, it } from "vitest";
import { z } from "zod";

import { mapError } from "../../../core/errors/map-error.js";
import { createSdkError } from "../../../core/errors/sdk-error.js";

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
});
