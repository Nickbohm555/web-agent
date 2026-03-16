import { ZodError } from "zod";

import { parseRetryAfter } from "../reliability/retry-after.js";
import { createSdkError, isSdkError, type SdkError } from "./sdk-error.js";

const TIMEOUT_ERROR_CODES = new Set([
  "ABORT_ERR",
  "ETIMEDOUT",
  "UND_ERR_BODY_TIMEOUT",
  "UND_ERR_CONNECT_TIMEOUT",
  "UND_ERR_HEADERS_TIMEOUT",
]);

const NETWORK_ERROR_CODES = new Set([
  "ECONNABORTED",
  "ECONNREFUSED",
  "ECONNRESET",
  "EAI_AGAIN",
  "ENOTFOUND",
  "EPIPE",
  "UND_ERR_SOCKET",
]);

const POLICY_DENIED_CODES = new Set([
  "DOMAIN_BLOCKED",
  "POLICY_DENIED",
  "ROBOTS_DENIED",
]);

const CONTENT_UNAVAILABLE_CODES = new Set([
  "BODY_TOO_LARGE",
  "CONTENT_UNAVAILABLE",
  "NOT_FOUND",
  "UNSUPPORTED_CONTENT_TYPE",
]);

interface ErrorLike {
  statusCode?: unknown;
  code?: unknown;
  retryAfter?: unknown;
  retryAfterMs?: unknown;
  message?: unknown;
  name?: unknown;
}

export function mapError(error: unknown): SdkError {
  if (isSdkError(error)) {
    return error;
  }

  if (error instanceof DOMException) {
    if (error.name === "TimeoutError") {
      return createSdkError({
        kind: "timeout",
        cause: error,
      });
    }

    if (error.name === "AbortError") {
      return createSdkError({
        kind: "timeout",
        cause: error,
      });
    }
  }

  if (error instanceof ZodError) {
    return createSdkError({
      kind: "invalid_request",
      cause: error,
    });
  }

  const errorLike = toErrorLike(error);
  const code = typeof errorLike.code === "string" ? errorLike.code : undefined;
  const statusCode = toStatusCode(errorLike.statusCode);
  const retryAfterMs = toRetryAfterMs(errorLike.retryAfterMs ?? errorLike.retryAfter);
  const errorName = typeof errorLike.name === "string" ? errorLike.name : undefined;

  if (errorName === "TimeoutError" || errorName === "AbortError") {
    return createSdkError({
      kind: "timeout",
      ...(statusCode !== undefined ? { statusCode } : {}),
      cause: error,
    });
  }

  if (statusCode === 429) {
    return createSdkError({
      kind: "rate_limited",
      statusCode,
      ...(retryAfterMs !== undefined ? { retryAfterMs } : {}),
      cause: error,
    });
  }

  if (code !== undefined && POLICY_DENIED_CODES.has(code)) {
    return createSdkError({
      kind: "policy_denied",
      ...(statusCode !== undefined ? { statusCode } : {}),
      cause: error,
    });
  }

  if (
    code !== undefined &&
    CONTENT_UNAVAILABLE_CODES.has(code)
  ) {
    return createSdkError({
      kind: "content_unavailable",
      ...(statusCode !== undefined ? { statusCode } : {}),
      cause: error,
    });
  }

  if (code !== undefined && TIMEOUT_ERROR_CODES.has(code)) {
    return createSdkError({
      kind: "timeout",
      ...(statusCode !== undefined ? { statusCode } : {}),
      cause: error,
    });
  }

  if (code !== undefined && NETWORK_ERROR_CODES.has(code)) {
    return createSdkError({
      kind: "network",
      ...(statusCode !== undefined ? { statusCode } : {}),
      cause: error,
    });
  }

  if (statusCode !== undefined) {
    return mapStatusCodeError(statusCode, retryAfterMs, error);
  }

  return createSdkError({
    kind: "unknown",
    cause: error,
  });
}

function mapStatusCodeError(
  statusCode: number,
  retryAfterMs: number | undefined,
  cause: unknown,
): SdkError {
  if (statusCode === 408) {
    return createSdkError({
      kind: "timeout",
      statusCode,
      cause,
    });
  }

  if ([500, 502, 503, 504].includes(statusCode)) {
    return createSdkError({
      kind: "provider_unavailable",
      statusCode,
      ...(retryAfterMs !== undefined ? { retryAfterMs } : {}),
      cause,
    });
  }

  if ([404, 410, 451].includes(statusCode)) {
    return createSdkError({
      kind: "content_unavailable",
      statusCode,
      cause,
    });
  }

  if ([400, 401, 402, 403, 405, 409, 413, 414, 415, 422, 431].includes(statusCode)) {
    return createSdkError({
      kind: "invalid_request",
      statusCode,
      cause,
    });
  }

  return createSdkError({
    kind: "unknown",
    statusCode,
    cause,
  });
}

function toErrorLike(error: unknown): ErrorLike {
  if (typeof error !== "object" || error === null) {
    return {};
  }

  return error as ErrorLike;
}

function toStatusCode(value: unknown): number | undefined {
  return typeof value === "number" && Number.isInteger(value) ? value : undefined;
}

function toRetryAfterMs(value: unknown): number | undefined {
  if (typeof value === "number" && Number.isFinite(value) && value >= 0) {
    return value;
  }

  if (typeof value === "string") {
    return parseRetryAfter(value);
  }

  return undefined;
}
