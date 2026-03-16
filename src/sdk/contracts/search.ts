import { z } from "zod";
import {
  resolveSearchControls,
  SearchControlsInputSchema,
  type ResolvedSearchControls,
} from "../../core/policy/retrieval-controls.js";

export const SearchOptionsSchema = SearchControlsInputSchema.transform((input) =>
  resolveSearchControls(input),
);

export const SearchQuerySchema = z.string().trim().min(1);

export const SearchRequestSchema = z
  .object({
    query: SearchQuerySchema,
    options: SearchControlsInputSchema.optional(),
  })
  .strict()
  .transform((input) => ({
    query: normalizeSearchQuery(input.query),
    options: normalizeSearchOptions(input.options),
  }));

export const SearchRankSchema = z
  .object({
    position: z.number().int().positive(),
    providerPosition: z.number().int().positive().optional(),
  })
  .strict();

export const SearchResultItemSchema = z
  .object({
    title: z.string().trim().min(1),
    url: z.string().trim().url(),
    snippet: z.string().trim().default(""),
    rank: SearchRankSchema,
  })
  .strict();

export const SearchResponseSchema = z
  .object({
    query: z.string().trim().min(1),
    results: z.array(SearchResultItemSchema),
    metadata: z
      .object({
        resultCount: z.number().int().nonnegative(),
      })
      .strict(),
  })
  .strict();

export type SearchOptions = z.input<typeof SearchOptionsSchema>;
export type NormalizedSearchOptions = ResolvedSearchControls;
export type SearchRequest = z.output<typeof SearchRequestSchema>;
export type SearchRank = z.output<typeof SearchRankSchema>;
export type SearchResultItem = z.output<typeof SearchResultItemSchema>;
export type SearchResponse = z.output<typeof SearchResponseSchema>;

export function normalizeSearchOptions(input?: unknown): NormalizedSearchOptions {
  return SearchOptionsSchema.parse(input ?? {});
}

export function normalizeSearchQuery(input: string): string {
  return SearchQuerySchema.parse(input);
}

export function normalizeSearchRequest(
  query: string,
  options?: unknown,
): SearchRequest {
  return SearchRequestSchema.parse({
    query,
    options: inputOrUndefined(options),
  });
}

export function normalizeSearchResponse(input: unknown): SearchResponse {
  return SearchResponseSchema.parse(input);
}

function inputOrUndefined(input: unknown): unknown {
  return input === undefined ? undefined : input;
}
