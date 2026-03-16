import { mapSerperOrganicToSearchResponse } from "../providers/serper/mapper.js";
import { callSerperSearch } from "../providers/serper/client.js";
import { filterSearchResultsByDomainScope } from "../providers/serper/search-result-filter.js";
import { buildCallMeta, startCallTimer } from "../core/telemetry/call-meta.js";
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
  const startedAt = startCallTimer();
  const normalizedQuery = normalizeSearchQuery(query);
  const normalizedOptions = normalizeSearchOptions(options);
  const providerStartedAt = startCallTimer();
  const { payload, meta: providerMeta } = await callSerperSearch(
    normalizedQuery,
    normalizedOptions,
  );
  const providerDurationMs = providerMeta.durationMs ?? startCallTimer() - providerStartedAt;
  const mappingStartedAt = startCallTimer();
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
    meta: buildCallMeta({
      operation: "search",
      startedAt,
      attempts: providerMeta.attempts,
      retries: providerMeta.retries,
      cacheHit: false,
      timings: {
        providerMs: providerDurationMs,
        mappingMs: startCallTimer() - mappingStartedAt,
      },
      usage: {
        provider: {
          organicResults: payload.organic.length,
        },
      },
    }),
    metadata: {
      resultCount: filteredResults.length,
    },
  };

  return normalizeSearchResponse(response);
}
