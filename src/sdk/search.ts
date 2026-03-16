import { mapSerperOrganicToSearchResponse } from "../providers/serper/mapper.js";
import { callSerperSearch } from "../providers/serper/client.js";
import {
  type SearchOptions,
  type SearchResponse,
  normalizeSearchOptions,
  normalizeSearchQuery,
  normalizeSearchResponse,
} from "./contracts/search.js";

export async function search(
  query: string,
  options?: SearchOptions,
): Promise<SearchResponse> {
  const normalizedQuery = normalizeSearchQuery(query);
  const normalizedOptions = normalizeSearchOptions(options);
  const { payload } = await callSerperSearch(normalizedQuery, normalizedOptions);
  const response = mapSerperOrganicToSearchResponse(payload, {
    query: normalizedQuery,
    limit: normalizedOptions.maxResults,
  });

  return normalizeSearchResponse(response);
}
