import pino from "pino";
import { request, type Dispatcher } from "undici";

import { executeWithRetry } from "../core/retry.js";

type RequestLike = typeof request;

export type HttpWorkerState =
  | "OK"
  | "NETWORK_ERROR"
  | "HTTP_STATUS_ERROR"
  | "HTTP_STATUS_UNSUPPORTED";

export interface RunHttpWorkerOptions {
  requestFn?: RequestLike;
  dispatcher?: Dispatcher;
  timeoutMs?: number;
  maxBytes?: number;
}

export interface HttpWorkerMeta {
  attempts: number;
  retries: number;
  durationMs: number;
}

export interface HttpWorkerSuccessResult {
  state: "OK";
  url: string;
  finalUrl: string;
  statusCode: number;
  contentType: string | null;
  body: string;
  meta: HttpWorkerMeta;
}

export interface HttpWorkerNetworkErrorResult {
  state: "NETWORK_ERROR";
  url: string;
  finalUrl: string | null;
  statusCode: null;
  contentType: null;
  body: null;
  errorClass: string;
  meta: HttpWorkerMeta;
}

export interface HttpWorkerStatusErrorResult {
  state: "HTTP_STATUS_ERROR";
  url: string;
  finalUrl: string;
  statusCode: number;
  contentType: string | null;
  body: null;
  errorClass: string;
  meta: HttpWorkerMeta;
}

export interface HttpWorkerUnsupportedStatusResult {
  state: "HTTP_STATUS_UNSUPPORTED";
  url: string;
  finalUrl: string;
  statusCode: number;
  contentType: string | null;
  body: null;
  errorClass: string;
  meta: HttpWorkerMeta;
}

export type HttpWorkerResult =
  | HttpWorkerSuccessResult
  | HttpWorkerNetworkErrorResult
  | HttpWorkerStatusErrorResult
  | HttpWorkerUnsupportedStatusResult;

const DEFAULT_TIMEOUT_MS = 10_000;
const DEFAULT_MAX_BYTES = 1_000_000;
const logger = pino({ level: process.env.LOG_LEVEL ?? "silent" });

export async function runHttpWorker(
  url: string,
  options: RunHttpWorkerOptions = {},
): Promise<HttpWorkerResult> {
  const normalizedUrl = new URL(url).toString();
  const requestFn = options.requestFn ?? request;
  const startedAt = Date.now();

  try {
    const result = await executeWithRetry(
      async () => {
        const response = await requestFn(normalizedUrl, {
          method: "GET",
          headersTimeout: options.timeoutMs ?? DEFAULT_TIMEOUT_MS,
          bodyTimeout: options.timeoutMs ?? DEFAULT_TIMEOUT_MS,
          ...(options.dispatcher ? { dispatcher: options.dispatcher } : {}),
        });

        if (response.statusCode === 429 || response.statusCode >= 500) {
          throw new RetryableHttpStatusError(response.statusCode);
        }

        if (response.statusCode < 200 || response.statusCode >= 300) {
          throw new NonRetryableHttpStatusError(response.statusCode);
        }

        const contentType = readHeader(response.headers["content-type"]);
        const body = await response.body.text();

        if (Buffer.byteLength(body, "utf8") > (options.maxBytes ?? DEFAULT_MAX_BYTES)) {
          throw new NonRetryableHttpStatusError(response.statusCode, "BodyTooLarge");
        }

        return {
          finalUrl: normalizedUrl,
          statusCode: response.statusCode,
          contentType,
          body,
        };
      },
      (error) => {
        if (error instanceof RetryableHttpStatusError) {
          return {
            retryable: true,
            reason: "retryable-status",
          };
        }

        if (error instanceof NonRetryableHttpStatusError) {
          return {
            retryable: false,
            reason: "non-retryable-status",
          };
        }

        return {
          retryable: isRetryableTransportError(error),
          reason: "transport-error",
        };
      },
    );

    const meta = createMeta(startedAt, result.attempts, result.retries);
    const success: HttpWorkerSuccessResult = {
      state: "OK",
      url: normalizedUrl,
      finalUrl: result.value.finalUrl,
      statusCode: result.value.statusCode,
      contentType: result.value.contentType,
      body: result.value.body,
      meta,
    };

    logger.info({
      operation: "fetch.http",
      durationMs: meta.durationMs,
      retryCount: meta.retries,
      errorClass: null,
      state: success.state,
      statusCode: success.statusCode,
    });

    return success;
  } catch (error) {
    const meta = createMeta(startedAt, getAttempts(error), Math.max(0, getAttempts(error) - 1));
    const result = toFailureResult(normalizedUrl, error, meta);

    logger.error({
      operation: "fetch.http",
      durationMs: meta.durationMs,
      retryCount: meta.retries,
      errorClass: result.errorClass,
      state: result.state,
      statusCode: result.statusCode,
    });

    return result;
  }
}

function toFailureResult(
  url: string,
  error: unknown,
  meta: HttpWorkerMeta,
): HttpWorkerNetworkErrorResult | HttpWorkerStatusErrorResult | HttpWorkerUnsupportedStatusResult {
  const unwrappedError = unwrapAbortCause(error);

  if (unwrappedError instanceof RetryableHttpStatusError) {
    return {
      state: "HTTP_STATUS_ERROR",
      url,
      finalUrl: url,
      statusCode: unwrappedError.statusCode,
      contentType: null,
      body: null,
      errorClass: unwrappedError.name,
      meta,
    };
  }

  if (unwrappedError instanceof NonRetryableHttpStatusError) {
    return {
      state: unwrappedError.statusCode >= 400 ? "HTTP_STATUS_UNSUPPORTED" : "HTTP_STATUS_ERROR",
      url,
      finalUrl: url,
      statusCode: unwrappedError.statusCode,
      contentType: null,
      body: null,
      errorClass: unwrappedError.name,
      meta,
    };
  }

  const resolvedErrorClass = unwrappedError instanceof Error
    ? unwrappedError.constructor.name
    : "UnknownError";

  return {
    state: "NETWORK_ERROR",
    url,
    finalUrl: null,
    statusCode: null,
    contentType: null,
    body: null,
    errorClass: resolvedErrorClass,
    meta,
  };
}

function createMeta(
  startedAt: number,
  attempts: number,
  retries: number,
): HttpWorkerMeta {
  return {
    attempts,
    retries,
    durationMs: Date.now() - startedAt,
  };
}

function getAttempts(error: unknown): number {
  if (error instanceof Error && "attemptNumber" in error) {
    const attemptNumber = error.attemptNumber;

    if (typeof attemptNumber === "number" && Number.isFinite(attemptNumber)) {
      return attemptNumber;
    }
  }

  return 1;
}

function isRetryableTransportError(error: unknown): boolean {
  if (!(error instanceof Error)) {
    return false;
  }

  const code = "code" in error ? error.code : undefined;

  return typeof code === "string" && new Set([
    "ECONNRESET",
    "ECONNREFUSED",
    "EPIPE",
    "ETIMEDOUT",
    "UND_ERR_CONNECT_TIMEOUT",
    "UND_ERR_HEADERS_TIMEOUT",
    "UND_ERR_BODY_TIMEOUT",
  ]).has(code);
}

function unwrapAbortCause(error: unknown): unknown {
  if (error instanceof Error && "originalError" in error) {
    return error.originalError;
  }

  if (error instanceof Error && "cause" in error && error.cause) {
    return error.cause;
  }

  return error;
}

function readHeader(headerValue: string | string[] | undefined): string | null {
  if (Array.isArray(headerValue)) {
    return headerValue[0] ?? null;
  }

  return typeof headerValue === "string" && headerValue.length > 0 ? headerValue : null;
}

class RetryableHttpStatusError extends Error {
  constructor(readonly statusCode: number) {
    super(`Retryable HTTP status ${statusCode}`);
    this.name = "RetryableHttpStatusError";
  }
}

class NonRetryableHttpStatusError extends Error {
  constructor(
    readonly statusCode: number,
    name = "NonRetryableHttpStatusError",
  ) {
    super(`Non-retryable HTTP status ${statusCode}`);
    this.name = name;
  }
}
