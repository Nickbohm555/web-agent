import { z } from "zod";

const SEARCH_LIMIT_DEFAULT = 10;
const SEARCH_LIMIT_MIN = 1;
const SEARCH_LIMIT_MAX = 20;

const RawSearchOptionsSchema = z
  .object({
    limit: z.coerce.number().int().min(SEARCH_LIMIT_MIN).max(SEARCH_LIMIT_MAX).optional(),
    country: z.string().trim().min(1).optional(),
    language: z.string().trim().min(1).optional(),
  })
  .strict();

export const SearchOptionsSchema = RawSearchOptionsSchema.transform((input) => ({
  limit: input.limit ?? SEARCH_LIMIT_DEFAULT,
  ...(input.country ? { country: input.country.toUpperCase() } : {}),
  ...(input.language ? { language: input.language.toLowerCase() } : {}),
}));

export const SearchRequestSchema = z
  .object({
    query: z.string().trim().min(1),
    options: RawSearchOptionsSchema.optional(),
  })
  .strict()
  .transform((input) => ({
    query: input.query,
    options: normalizeSearchOptions(input.options),
  }));

export const SearchRankSchema = z
  .object({
    position: z.number().int().positive(),
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

export type SearchOptions = z.output<typeof SearchOptionsSchema>;
export type SearchRequest = z.output<typeof SearchRequestSchema>;
export type SearchRank = z.output<typeof SearchRankSchema>;
export type SearchResultItem = z.output<typeof SearchResultItemSchema>;
export type SearchResponse = z.output<typeof SearchResponseSchema>;

export function normalizeSearchOptions(input?: unknown): SearchOptions {
  return SearchOptionsSchema.parse(input ?? {});
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
