import {
  type FetchFallbackReason,
  type FetchMetadata,
  type FetchResponse,
} from "../sdk/contracts/fetch.js";
import { normalizeUrl } from "../sdk/contracts/fetch.js";
import { createSdkError, type SdkError } from "../core/errors/sdk-error.js";
import { buildCallMeta, startCallTimer } from "../core/telemetry/call-meta.js";
import {
  extractContent,
  type ExtractContentResult,
} from "./extract.js";
import {
  evaluateRobots,
  type EvaluateRobotsOptions,
  type RobotsPolicyResult,
} from "./robots.js";
import {
  runHttpWorker,
  type HttpWorkerResult,
  type RunHttpWorkerOptions,
} from "./http-worker.js";

export interface RunFetchOrchestratorOptions {
  userAgent?: string;
  robots?: Omit<EvaluateRobotsOptions, "userAgent">;
  http?: RunHttpWorkerOptions;
  extraction?: {
    minTextLength?: number;
  };
  evaluateRobotsFn?: (
    targetUrl: string,
    options?: EvaluateRobotsOptions,
  ) => Promise<RobotsPolicyResult>;
  runHttpWorkerFn?: (
    targetUrl: string,
    options?: RunHttpWorkerOptions,
  ) => Promise<HttpWorkerResult>;
  extractContentFn?: (
    html: string,
    contentType: string | null,
    options?: { minTextLength?: number },
  ) => ExtractContentResult;
}

export async function runFetchOrchestrator(
  url: string,
  options: RunFetchOrchestratorOptions = {},
): Promise<FetchResponse> {
  const normalizedUrl = normalizeUrl(url);
  const startedAt = startCallTimer();
  const robotsStartedAt = startCallTimer();
  const evaluateRobotsFn = options.evaluateRobotsFn ?? evaluateRobots;
  const runHttpWorkerFn = options.runHttpWorkerFn ?? runHttpWorker;
  const extractContentFn = options.extractContentFn ?? extractContent;

  const robots = await evaluateRobotsFn(normalizedUrl, {
    ...options.robots,
    ...(options.userAgent ? { userAgent: options.userAgent } : {}),
  });

  if (!robots.canFetch) {
    throw createFetchError({
      kind: "policy_denied",
      startedAt,
      attempts: 1,
      retries: 0,
      timings: {
        robotsMs: startCallTimer() - robotsStartedAt,
      },
      finalUrl: normalizedUrl,
      contentType: null,
      statusCode: null,
      fallbackReason: null,
    });
  }

  const httpStartedAt = startCallTimer();
  const httpResult = await runHttpWorkerFn(normalizedUrl, options.http);
  const httpDurationMs = startCallTimer() - httpStartedAt;

  if (httpResult.state !== "OK") {
    throw createFetchError({
      kind: httpResult.errorKind,
      startedAt,
      attempts: httpResult.meta.attempts,
      retries: httpResult.meta.retries,
      timings: {
        robotsMs: startCallTimer() - robotsStartedAt,
        httpMs: httpDurationMs,
      },
      finalUrl: httpResult.finalUrl ?? normalizedUrl,
      contentType: httpResult.contentType,
      statusCode: httpResult.statusCode,
      fallbackReason: mapHttpFailureToFallbackReason(httpResult.state),
    });
  }

  const extractionStartedAt = startCallTimer();
  const extraction = extractContentFn(httpResult.body, httpResult.contentType, options.extraction);
  const extractionDurationMs = startCallTimer() - extractionStartedAt;

  if (extraction.state === "UNSUPPORTED_CONTENT_TYPE") {
    return createResponse(normalizedUrl, {
      startedAt,
      attempts: httpResult.meta.attempts,
      retries: httpResult.meta.retries,
      timings: {
        robotsMs: startCallTimer() - robotsStartedAt,
        httpMs: httpDurationMs,
        extractionMs: extractionDurationMs,
      },
      finalUrl: httpResult.finalUrl,
      contentType: httpResult.contentType,
      statusCode: httpResult.statusCode,
      fallbackReason: "browser-required",
    });
  }

  if (extraction.state === "LOW_CONTENT_QUALITY") {
    return createResponse(normalizedUrl, {
      startedAt,
      attempts: httpResult.meta.attempts,
      retries: httpResult.meta.retries,
      timings: {
        robotsMs: startCallTimer() - robotsStartedAt,
        httpMs: httpDurationMs,
        extractionMs: extractionDurationMs,
      },
      finalUrl: httpResult.finalUrl,
      contentType: httpResult.contentType,
      statusCode: httpResult.statusCode,
      text: extraction.text,
      markdown: extraction.markdown,
      fallbackReason: "low-content-quality",
    });
  }

  return createResponse(normalizedUrl, {
    startedAt,
    attempts: httpResult.meta.attempts,
    retries: httpResult.meta.retries,
    timings: {
      robotsMs: startCallTimer() - robotsStartedAt,
      httpMs: httpDurationMs,
      extractionMs: extractionDurationMs,
    },
    finalUrl: httpResult.finalUrl,
    contentType: httpResult.contentType,
    statusCode: httpResult.statusCode,
    text: extraction.text,
    markdown: extraction.markdown,
    fallbackReason: null,
  });
}

function createResponse(
  url: string,
  input: {
    startedAt: number;
    attempts: number;
    retries: number;
    timings: Record<string, number>;
    finalUrl: string;
    contentType: string | null;
    statusCode: number | null;
    text?: string;
    markdown?: string;
    fallbackReason: FetchFallbackReason | null;
  },
): FetchResponse {
  return {
    url,
    text: input.text ?? "",
    markdown: input.markdown ?? "",
    meta: buildCallMeta({
      operation: "fetch",
      startedAt: input.startedAt,
      attempts: input.attempts,
      retries: input.retries,
      cacheHit: false,
      timings: input.timings,
      usage: {
        content: {
          textChars: (input.text ?? "").length,
          markdownChars: (input.markdown ?? "").length,
        },
      },
    }),
    metadata: {
      finalUrl: input.finalUrl,
      contentType: input.contentType,
      statusCode: input.statusCode,
    },
    fallbackReason: input.fallbackReason,
  };
}

function createFetchError(input: {
  kind: SdkError["kind"];
  startedAt: number;
  attempts: number;
  retries: number;
  timings: Record<string, number>;
  finalUrl: string;
  contentType: string | null;
  statusCode: number | null;
  fallbackReason: FetchFallbackReason | null;
}): SdkError {
  const error = createSdkError({
    kind: input.kind,
    ...(input.statusCode !== null ? { statusCode: input.statusCode } : {}),
  });

  Object.defineProperties(error, {
    attemptNumber: {
      value: input.attempts,
      enumerable: false,
      writable: true,
      configurable: true,
    },
    operation: {
      value: "fetch",
      enumerable: true,
      writable: false,
      configurable: false,
    },
    fallbackReason: {
      value: input.fallbackReason,
      enumerable: true,
      writable: false,
      configurable: false,
    },
    meta: {
      value: buildCallMeta({
        operation: "fetch",
        startedAt: input.startedAt,
        attempts: input.attempts,
        retries: input.retries,
        cacheHit: false,
        timings: input.timings,
      }),
      enumerable: true,
      writable: false,
      configurable: false,
    },
    metadata: {
      value: createFetchMetadata(
        input.finalUrl,
        input.contentType,
        input.statusCode,
      ),
      enumerable: true,
      writable: false,
      configurable: false,
    },
  });

  return error;
}

function createFetchMetadata(
  finalUrl: string,
  contentType: string | null,
  statusCode: number | null,
): FetchMetadata {
  return {
    finalUrl,
    contentType,
    statusCode,
  };
}

function mapHttpFailureToFallbackReason(
  state: HttpWorkerResult["state"],
): FetchFallbackReason {
  if (state === "NETWORK_ERROR") {
    return "network-error";
  }

  return "browser-required";
}
