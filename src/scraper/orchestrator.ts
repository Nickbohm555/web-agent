import type { FetchFallbackReason, FetchResponse } from "../sdk/contracts/fetch.js";
import { normalizeUrl } from "../sdk/contracts/fetch.js";
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
    return createResponse(normalizedUrl, {
      startedAt,
      attempts: 1,
      retries: 0,
      cacheHit: false,
      timings: {
        robotsMs: startCallTimer() - robotsStartedAt,
      },
      finalUrl: normalizedUrl,
      contentType: null,
      statusCode: null,
      fallbackReason: "browser-required",
    });
  }

  const httpStartedAt = startCallTimer();
  const httpResult = await runHttpWorkerFn(normalizedUrl, options.http);
  const httpDurationMs = startCallTimer() - httpStartedAt;

  if (httpResult.state !== "OK") {
    return createResponse(normalizedUrl, {
      startedAt,
      attempts: httpResult.meta.attempts,
      retries: httpResult.meta.retries,
      cacheHit: false,
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
      cacheHit: false,
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
      cacheHit: false,
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
    cacheHit: false,
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
    cacheHit: boolean;
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
      cacheHit: input.cacheHit,
      timings: input.timings,
    }),
    metadata: {
      finalUrl: input.finalUrl,
      contentType: input.contentType,
      statusCode: input.statusCode,
    },
    fallbackReason: input.fallbackReason,
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
