import { mapSerperOrganicToSearchResponse } from "../providers/serper/mapper.js";
import { callSerperSearch } from "../providers/serper/client.js";
import { filterSearchResultsByDomainScope } from "../providers/serper/search-result-filter.js";
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
  const mappedResponse = mapSerperOrganicToSearchResponse(payload, {
    query: normalizedQuery,
    limit: payload.organic.length,
  });
  const filteredResults = filterSearchResultsByDomainScope(
    mappedResponse.results,
    normalizedOptions.domainScope,
  ).slice(0, normalizedOptions.maxResults);
  const response = {
    ...mappedResponse,
    results: filteredResults.map((entry, index) => ({
      ...entry,
      rank: {
        position: index + 1,
        providerPosition: entry.rank.providerPosition,
      },
    })),
    metadata: {
      resultCount: filteredResults.length,
    },
  };

  return normalizeSearchResponse(response);
}
