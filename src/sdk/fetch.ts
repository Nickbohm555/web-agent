import {
  type FetchOptions,
  type FetchResponse,
  normalizeFetchRequest,
  normalizeFetchResponse,
} from "./contracts/fetch.js";
import { runFetchOrchestrator } from "../scraper/orchestrator.js";

export async function fetch(
  url: string,
  options?: FetchOptions,
): Promise<FetchResponse> {
  const request = normalizeFetchRequest(url, options);
  const response = await runFetchOrchestrator(request.url, {
    http: {
      timeoutMs: request.options.timeoutMs,
    },
  });

  return normalizeFetchResponse(response);
}
