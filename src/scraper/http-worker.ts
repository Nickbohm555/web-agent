import pino from "pino";
import { request, type Dispatcher } from "undici";

import { createFetchSafetyError, type FetchSafetyError } from "../core/errors/fetch-safety-error.js";
import { mapError } from "../core/errors/map-error.js";
import type { SdkErrorKind } from "../core/errors/sdk-error.js";
import {
  validateRedirectTarget,
} from "../core/network/redirect-guard.js";
import { executeWithRetry } from "../core/reliability/execute-with-retry.js";
import type { RetryPolicy } from "../core/reliability/execute-with-retry.js";

type RequestLike = typeof request;
type ValidateRedirectTargetFn = typeof validateRedirectTarget;

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
  retryPolicy?: RetryPolicy;
  maxRedirects?: number;
  validateRedirectTargetFn?: ValidateRedirectTargetFn;
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
  errorKind: SdkErrorKind;
  retryable: boolean;
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
  errorKind: SdkErrorKind;
  retryable: boolean;
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
  errorKind: SdkErrorKind;
  retryable: boolean;
  safetyDecision?: FetchSafetyError["decision"];
  meta: HttpWorkerMeta;
}

export type HttpWorkerResult =
  | HttpWorkerSuccessResult
  | HttpWorkerNetworkErrorResult
  | HttpWorkerStatusErrorResult
  | HttpWorkerUnsupportedStatusResult;

const DEFAULT_TIMEOUT_MS = 10_000;
const DEFAULT_MAX_BYTES = 1_000_000;
const DEFAULT_MAX_REDIRECTS = 5;
const logger = pino({ level: process.env.LOG_LEVEL ?? "silent" });

export async function runHttpWorker(
  url: string,
  options: RunHttpWorkerOptions = {},
): Promise<HttpWorkerResult> {
  const normalizedUrl = new URL(url).toString();
  const requestFn = options.requestFn ?? request;
  const validateRedirectTargetFn =
    options.validateRedirectTargetFn ?? validateRedirectTarget;
  const startedAt = Date.now();

  try {
    const result = await executeWithRetry(
      async () => {
        return runHttpRequestChain(normalizedUrl, {
          requestFn,
          timeoutMs: options.timeoutMs ?? DEFAULT_TIMEOUT_MS,
          maxBytes: options.maxBytes ?? DEFAULT_MAX_BYTES,
          maxRedirects: options.maxRedirects ?? DEFAULT_MAX_REDIRECTS,
          validateRedirectTargetFn,
          ...(options.dispatcher ? { dispatcher: options.dispatcher } : {}),
        });
      },
      options.retryPolicy,
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
  const sdkError = mapError(unwrapAbortCause(error));
  const failureMetadata = readFailureMetadata(error);
  const safetyDecision = readSafetyDecision(error);
  const failureBase = {
    errorClass: sdkError.name,
    errorKind: sdkError.kind,
    retryable: sdkError.retryable,
    meta,
  } as const;

  if (sdkError.kind === "rate_limited" || sdkError.kind === "provider_unavailable") {
    return {
      state: "HTTP_STATUS_ERROR",
      url,
      finalUrl: url,
      statusCode: sdkError.statusCode ?? 503,
      contentType: null,
      body: null,
      ...failureBase,
    };
  }

  if (
    sdkError.kind === "invalid_request" ||
    sdkError.kind === "policy_denied" ||
    sdkError.kind === "content_unavailable"
  ) {
    return {
      state: "HTTP_STATUS_UNSUPPORTED",
      url,
      finalUrl: failureMetadata.finalUrl ?? url,
      statusCode: sdkError.statusCode ?? failureMetadata.statusCode ?? 400,
      contentType: failureMetadata.contentType,
      body: null,
      ...(safetyDecision ? { safetyDecision } : {}),
      ...failureBase,
    };
  }

  return {
    state: "NETWORK_ERROR",
    url,
    finalUrl: null,
    statusCode: null,
    contentType: null,
    body: null,
    ...failureBase,
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

async function runHttpRequestChain(
  url: string,
  options: {
    requestFn: RequestLike;
    dispatcher?: Dispatcher;
    timeoutMs: number;
    maxBytes: number;
    maxRedirects: number;
    validateRedirectTargetFn: ValidateRedirectTargetFn;
  },
): Promise<{
  finalUrl: string;
  statusCode: number;
  contentType: string | null;
  body: string;
}> {
  let currentUrl = url;
  let redirectCount = 0;

  while (true) {
    const response = await options.requestFn(currentUrl, {
      method: "GET",
      headersTimeout: options.timeoutMs,
      bodyTimeout: options.timeoutMs,
      ...(options.dispatcher ? { dispatcher: options.dispatcher } : {}),
    });

    if (isRedirectStatus(response.statusCode)) {
      const location = readHeader(response.headers?.location);

      if (!location) {
        throw createRedirectSafetyError(currentUrl, "UNSAFE_REDIRECT");
      }

      if (redirectCount >= options.maxRedirects) {
        throw createRedirectSafetyError(new URL(location, currentUrl).toString(), "UNSAFE_REDIRECT");
      }

      const redirectDecision = await options.validateRedirectTargetFn(currentUrl, location);

      if (redirectDecision.outcome === "deny") {
        throw createFetchSafetyError({
          decision: redirectDecision.decision,
        });
      }

      currentUrl = redirectDecision.redirectUrl;
      redirectCount += 1;
      continue;
    }

    if (response.statusCode === 429 || response.statusCode >= 500) {
      throw {
        statusCode: response.statusCode,
        retryAfter: readHeader(response.headers?.["retry-after"]),
      };
    }

    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw {
        statusCode: response.statusCode,
      };
    }

    const contentType = readHeader(response.headers["content-type"]);
    const body = await response.body.text();

    if (Buffer.byteLength(body, "utf8") > options.maxBytes) {
      throw {
        statusCode: response.statusCode,
        code: "BODY_TOO_LARGE",
      };
    }

    return {
      finalUrl: currentUrl,
      statusCode: response.statusCode,
      contentType,
      body,
    };
  }
}

function isRedirectStatus(statusCode: number): boolean {
  return [301, 302, 303, 307, 308].includes(statusCode);
}

function createRedirectSafetyError(
  redirectUrl: string,
  reason: "UNSAFE_REDIRECT",
): FetchSafetyError {
  const parsedUrl = new URL(redirectUrl);

  return createFetchSafetyError({
    decision: {
      stage: "redirect_preflight",
      outcome: "deny",
      reason,
      target: {
        url: redirectUrl,
        scheme: parsedUrl.protocol.replace(/:$/, ""),
        hostname: parsedUrl.hostname || null,
        port: readPort(parsedUrl),
      },
    },
  });
}

function readFailureMetadata(error: unknown): {
  finalUrl: string | null;
  contentType: string | null;
  statusCode: number | null;
} {
  if (
    typeof error === "object" &&
    error !== null &&
    "metadata" in error &&
    typeof error.metadata === "object" &&
    error.metadata !== null
  ) {
    const metadata = error.metadata as {
      finalUrl?: unknown;
      contentType?: unknown;
      statusCode?: unknown;
    };

    return {
      finalUrl: typeof metadata.finalUrl === "string" ? metadata.finalUrl : null,
      contentType: typeof metadata.contentType === "string" ? metadata.contentType : null,
      statusCode:
        typeof metadata.statusCode === "number" && Number.isInteger(metadata.statusCode)
          ? metadata.statusCode
          : null,
    };
  }

  return {
    finalUrl: null,
    contentType: null,
    statusCode: null,
  };
}

function readSafetyDecision(error: unknown): FetchSafetyError["decision"] | undefined {
  if (
    typeof error === "object" &&
    error !== null &&
    "decision" in error
  ) {
    const decision = (error as { decision?: unknown }).decision;

    if (
      typeof decision === "object" &&
      decision !== null &&
      "outcome" in decision &&
      "stage" in decision &&
      "target" in decision
    ) {
      return decision as FetchSafetyError["decision"];
    }
  }

  return undefined;
}

function readPort(url: URL): number | null {
  if (url.port) {
    return Number(url.port);
  }

  if (url.protocol === "http:") {
    return 80;
  }

  if (url.protocol === "https:") {
    return 443;
  }

  return null;
}
