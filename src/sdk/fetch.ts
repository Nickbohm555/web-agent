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
import { runFetchOrchestrator } from "../scraper/orchestrator.js";

const fetchCache = createFetchCache();

export async function fetch(
  url: string,
  options?: FetchOptions,
): Promise<FetchResponse> {
  const request = normalizeFetchRequest(url, options);
  const cacheReadPolicy = resolveFetchCacheReadPolicy(request.options);
  const cached = fetchCache.read(request, cacheReadPolicy);

  if (cached.kind === "hit") {
    return normalizeFetchResponse(cached.entry.response);
  }

  const response = await executeFetchRequest(request.url, request.options.timeoutMs);
  fetchCache.write(request, response);

  return normalizeFetchResponse(response);
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
