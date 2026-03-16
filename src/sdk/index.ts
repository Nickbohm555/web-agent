import {
  type FetchOptions,
  type FetchResponse,
  normalizeFetchRequest,
  normalizeFetchResponse,
} from "./contracts/fetch.js";
import {
  type SearchOptions,
  type SearchResponse,
  normalizeSearchRequest,
  normalizeSearchResponse,
} from "./contracts/search.js";

export * from "./contracts/fetch.js";
export * from "./contracts/search.js";

export async function search(
  query: string,
  options?: SearchOptions,
): Promise<SearchResponse> {
  const request = normalizeSearchRequest(query, options);

  return normalizeSearchResponse({
    query: request.query,
    results: [],
    metadata: {
      resultCount: 0,
    },
  });
}

export async function fetch(
  url: string,
  options?: FetchOptions,
): Promise<FetchResponse> {
  const request = normalizeFetchRequest(url, options);

  return normalizeFetchResponse({
    url: request.url,
    text: "",
    markdown: "",
    metadata: {
      finalUrl: request.url,
      contentType: null,
      statusCode: null,
    },
    fallbackReason: null,
  });
}
