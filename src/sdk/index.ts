import {
  type FetchOptions,
  type FetchResponse,
  normalizeFetchRequest,
  normalizeFetchResponse,
} from "./contracts/fetch.js";
import {
  type SearchOptions,
  type SearchResponse,
} from "./contracts/search.js";
import { search } from "./search.js";

export * from "./contracts/fetch.js";
export * from "./contracts/search.js";
export { search };

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
