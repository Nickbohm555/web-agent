import {
  type FetchOptions,
  type FetchResponse,
  normalizeFetchCacheControl,
  normalizeFetchRequest,
  normalizeFetchResponse,
} from "./contracts/fetch.js";
import { runFetchOrchestrator } from "../scraper/orchestrator.js";

export async function fetch(
  url: string,
  options?: FetchOptions,
): Promise<FetchResponse> {
  const request = normalizeFetchRequest(url, options);
  const cacheReadPolicy = resolveFetchCacheReadPolicy(request.options);
  const response = await executeFetchRequest(request.url, request.options.timeoutMs, cacheReadPolicy);

  return normalizeFetchResponse(response);
}

interface FetchCacheReadPolicy {
  mode: "eligible" | "bypass";
  maxAgeMs: number;
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
  cacheReadPolicy: FetchCacheReadPolicy,
): Promise<FetchResponse> {
  // Section 20 establishes precedence before retrieval begins; Section 21 adds
  // the concrete cache utility that consumes this policy.
  void cacheReadPolicy;

  return runFetchOrchestrator(url, {
    http: {
      timeoutMs,
    },
  });
}
