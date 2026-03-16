import {
  type FetchOptions,
  type FetchResponse,
  normalizeFetchCacheControl,
  normalizeFetchRequest,
  normalizeFetchResponse,
} from "./contracts/fetch.js";
import {
  createFetchCache,
  type FetchCacheReadPolicy,
} from "../core/cache/fetch-cache.js";
import { buildCallMeta, startCallTimer } from "../core/telemetry/call-meta.js";
import { runFetchOrchestrator } from "../scraper/orchestrator.js";

const fetchCache = createFetchCache();

export async function fetch(
  url: string,
  options?: FetchOptions,
): Promise<FetchResponse> {
  const startedAt = startCallTimer();
  const request = normalizeFetchRequest(url, options);
  const cacheReadPolicy = resolveFetchCacheReadPolicy(request.options);
  const cached = fetchCache.read(request, cacheReadPolicy);

  if (cached.kind === "hit") {
    return normalizeFetchResponse({
      ...cached.entry.response,
      meta: buildCallMeta({
        operation: "fetch",
        startedAt,
        attempts: cached.entry.response.meta.attempts,
        retries: cached.entry.response.meta.retries,
        cacheHit: true,
        timings: {
          cacheReadMs: startCallTimer() - startedAt,
          ...cached.entry.response.meta.timings,
        },
        ...(cached.entry.response.meta.usage
          ? { usage: cached.entry.response.meta.usage }
          : {}),
      }),
    });
  }

  const fetchStartedAt = startCallTimer();
  const response = await executeFetchRequest(request.url, request.options.timeoutMs);
  const normalizedResponse = normalizeFetchResponse({
    ...response,
    meta: buildCallMeta({
      operation: "fetch",
      startedAt,
      attempts: response.meta.attempts,
      retries: response.meta.retries,
      cacheHit: false,
      timings: {
        cacheReadMs: fetchStartedAt - startedAt,
        networkMs: startCallTimer() - fetchStartedAt,
        ...response.meta.timings,
      },
      ...(response.meta.usage ? { usage: response.meta.usage } : {}),
    }),
  });
  fetchCache.write(request, normalizedResponse);

  return normalizedResponse;
}

function resolveFetchCacheReadPolicy(
  options: FetchOptions,
): FetchCacheReadPolicy {
  const cacheControl = normalizeFetchCacheControl(options);

  if (cacheControl.fresh) {
    return {
      mode: "bypass",
      maxAgeMs: cacheControl.maxAgeMs,
    };
  }

  return {
    mode: "eligible",
    maxAgeMs: cacheControl.maxAgeMs,
  };
}

async function executeFetchRequest(
  url: string,
  timeoutMs: number,
): Promise<FetchResponse> {
  return runFetchOrchestrator(url, {
    http: {
      timeoutMs,
    },
  });
}
