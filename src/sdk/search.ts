import { mapSerperOrganicToSearchResponse } from "../providers/serper/mapper.js";
import { callSerperSearch } from "../providers/serper/client.js";
import {
  type SearchOptions,
  type SearchResponse,
  normalizeSearchRequest,
  normalizeSearchResponse,
} from "./contracts/search.js";

export async function search(
  query: string,
  options?: SearchOptions,
): Promise<SearchResponse> {
  const request = normalizeSearchRequest(query, options);
  const { payload } = await callSerperSearch(request.query, request.options);
  const response = mapSerperOrganicToSearchResponse(payload, {
    query: request.query,
    limit: request.options.limit,
  });

  return normalizeSearchResponse(response);
}
