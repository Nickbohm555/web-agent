import {
  type SearchResultItem,
  normalizeSearchResponse,
  type SearchResponse,
} from "../../sdk/contracts/search.js";
import { buildCallMeta } from "../../core/telemetry/call-meta.js";
import type { SerperSearchResponse } from "./client.js";

export interface MapSerperOrganicOptions {
  query: string;
  limit: number;
}

export function mapSerperOrganicToSearchResponse(
  payload: SerperSearchResponse,
  options: MapSerperOrganicOptions,
): SearchResponse {
  const results = payload.organic
    .map((entry, index) => normalizeOrganicResult(entry, index))
    .filter((entry): entry is SearchResultItem => entry !== null)
    .slice(0, options.limit)
    .map((entry, index) => ({
      ...entry,
      rank: {
        position: index + 1,
        providerPosition: entry.rank.providerPosition,
      },
    }));

  return normalizeSearchResponse({
    query: options.query,
    results,
    meta: buildCallMeta({
      operation: "search",
      startedAt: 0,
      endedAt: 0,
      attempts: 1,
      retries: 0,
      cacheHit: false,
      timings: {},
    }),
    metadata: {
      resultCount: results.length,
    },
  });
}

function normalizeOrganicResult(
  entry: SerperSearchResponse["organic"][number],
  index: number,
): SearchResultItem | null {
  const title = entry.title?.trim() ?? "";
  const url = normalizeUrl(entry.link);

  if (!title || !url) {
    return null;
  }

  return {
    title,
    url,
    snippet: entry.snippet?.trim() ?? "",
    rank: {
      position: index + 1,
      providerPosition: entry.position ?? index + 1,
    },
  };
}

function normalizeUrl(input: string | undefined): string | null {
  const value = input?.trim();

  if (!value) {
    return null;
  }

  try {
    return new URL(value).toString();
  } catch {
    return null;
  }
}
