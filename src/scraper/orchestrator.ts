import {
  type FetchFallbackReason,
  type FetchMetadata,
  type FetchResponse,
} from "../sdk/contracts/fetch.js";
import { normalizeUrl } from "../sdk/contracts/fetch.js";
import {
  type ComplianceDecision,
  type SafetyDecision,
} from "../sdk/contracts/safety.js";
import {
  createFetchSafetyError,
  type BlockedFetchDecision,
} from "../core/errors/fetch-safety-error.js";
import { createSdkError, type SdkError } from "../core/errors/sdk-error.js";
import { resolveAndClassifyTarget } from "../core/network/resolve-and-classify.js";
import { evaluateSafetyPreflight } from "../core/policy/safety-decision.js";
import { buildCallMeta, startCallTimer } from "../core/telemetry/call-meta.js";
import {
  extractContent,
  type ExtractContentResult,
} from "./extract.js";
import {
  evaluateRobotsCompliance,
  type EvaluateRobotsComplianceOptions,
  type RobotsComplianceResult,
} from "./robots/evaluator.js";
import {
  runHttpWorker,
  type HttpWorkerResult,
  type RunHttpWorkerOptions,
} from "./http-worker.js";

export interface RunFetchOrchestratorOptions {
  userAgent?: string;
  robots?: Omit<EvaluateRobotsComplianceOptions, "userAgent">;
  http?: RunHttpWorkerOptions;
  extraction?: {
    minTextLength?: number;
  };
  evaluateSafetyPreflightFn?: typeof evaluateSafetyPreflight;
  resolveAndClassifyTargetFn?: typeof resolveAndClassifyTarget;
  evaluateRobotsComplianceFn?: (
    targetUrl: string,
    options?: EvaluateRobotsComplianceOptions,
  ) => Promise<RobotsComplianceResult>;
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
  const safetyStartedAt = startCallTimer();
  const evaluateSafetyPreflightFn =
    options.evaluateSafetyPreflightFn ?? evaluateSafetyPreflight;
  const resolveAndClassifyTargetFn =
    options.resolveAndClassifyTargetFn ?? resolveAndClassifyTarget;
  const evaluateRobotsComplianceFn =
    options.evaluateRobotsComplianceFn ?? evaluateRobotsCompliance;
  const runHttpWorkerFn = options.runHttpWorkerFn ?? runHttpWorker;
  const extractContentFn = options.extractContentFn ?? extractContent;
  const urlDecision = evaluateSafetyPreflightFn(normalizedUrl);

  if (urlDecision.outcome === "deny") {
    throw createFetchSafetyError({
      decision: urlDecision,
      timings: {
        safetyMs: startCallTimer() - safetyStartedAt,
      },
      startedAt,
      attempts: 1,
      retries: 0,
    });
  }

  const networkDecision = await resolveAndClassifyTargetFn(urlDecision.target);

  if (networkDecision.outcome === "deny") {
    throw createFetchSafetyError({
      decision: networkDecision.decision,
      safetyDecision: networkDecision.decision,
      timings: {
        safetyMs: startCallTimer() - safetyStartedAt,
      },
      startedAt,
      attempts: 1,
      retries: 0,
    });
  }

  const safetyDurationMs = startCallTimer() - safetyStartedAt;
  const robotsStartedAt = startCallTimer();
  const robots = await evaluateRobotsComplianceFn(normalizedUrl, {
    ...options.robots,
    ...(options.userAgent ? { userAgent: options.userAgent } : {}),
  });

  if (robots.outcome === "DENY" || robots.outcome === "UNAVAILABLE") {
    const blockedDecision = robots.decision as BlockedFetchDecision;
    const complianceDecision = robots.decision as Extract<
      ComplianceDecision,
      { outcome: "deny" | "unavailable" }
    >;

    throw createFetchSafetyError({
      decision: blockedDecision,
      safetyDecision: networkDecision.decision,
      complianceDecision,
      startedAt,
      attempts: 1,
      retries: 0,
      timings: {
        safetyMs: safetyDurationMs,
        robotsMs: startCallTimer() - robotsStartedAt,
      },
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
        safetyMs: safetyDurationMs,
        robotsMs: startCallTimer() - robotsStartedAt,
        httpMs: httpDurationMs,
      },
      finalUrl: httpResult.finalUrl ?? normalizedUrl,
      contentType: httpResult.contentType,
      statusCode: httpResult.statusCode,
      fallbackReason: mapHttpFailureToFallbackReason(httpResult.state),
      safetyDecision: networkDecision.decision,
      complianceDecision: robots.decision,
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
        safetyMs: safetyDurationMs,
        robotsMs: startCallTimer() - robotsStartedAt,
        httpMs: httpDurationMs,
        extractionMs: extractionDurationMs,
      },
      finalUrl: httpResult.finalUrl,
      contentType: httpResult.contentType,
      statusCode: httpResult.statusCode,
      fallbackReason: "browser-required",
      safetyDecision: networkDecision.decision,
      complianceDecision: robots.decision,
    });
  }

  if (extraction.state === "LOW_CONTENT_QUALITY") {
    return createResponse(normalizedUrl, {
      startedAt,
      attempts: httpResult.meta.attempts,
      retries: httpResult.meta.retries,
      timings: {
        safetyMs: safetyDurationMs,
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
      safetyDecision: networkDecision.decision,
      complianceDecision: robots.decision,
    });
  }

  return createResponse(normalizedUrl, {
    startedAt,
    attempts: httpResult.meta.attempts,
    retries: httpResult.meta.retries,
    timings: {
      safetyMs: safetyDurationMs,
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
    safetyDecision: networkDecision.decision,
    complianceDecision: robots.decision,
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
    safetyDecision?: SafetyDecision | null;
    complianceDecision?: ComplianceDecision | null;
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
      decisions: {
        safety: input.safetyDecision ?? null,
        compliance: input.complianceDecision ?? null,
      },
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
  safetyDecision?: SafetyDecision | null;
  complianceDecision?: ComplianceDecision | null;
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
        input.safetyDecision ?? null,
        input.complianceDecision ?? null,
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
  safetyDecision: SafetyDecision | null = null,
  complianceDecision: ComplianceDecision | null = null,
): FetchMetadata {
  return {
    finalUrl,
    contentType,
    statusCode,
    decisions: {
      safety: safetyDecision,
      compliance: complianceDecision,
    },
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
