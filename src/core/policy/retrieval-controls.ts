import { z } from "zod";
import {
  resolveDomainScope,
  type ResolvedDomainScope,
} from "./domain-scope.js";

const SEARCH_RESULTS_DEFAULT = 10;
const SEARCH_RESULTS_MIN = 1;
const SEARCH_RESULTS_MAX = 20;

const TIMEOUT_DEFAULT_MS = 5_000;
const TIMEOUT_MIN_MS = 250;
const TIMEOUT_MAX_MS = 30_000;

const FETCH_MAX_AGE_DEFAULT_MS = 5 * 60 * 1000;
const FETCH_MAX_AGE_MAX_MS = 24 * 60 * 60 * 1000;

export const RetrievalFreshnessSchema = z.enum([
  "any",
  "day",
  "week",
  "month",
  "year",
]);

const LocaleSchema = z.object({
  country: z.string().trim().min(1).default("us"),
  language: z.string().trim().min(1).default("en"),
});

export const SearchControlsInputSchema = z
  .object({
    limit: z.coerce.number().int().min(SEARCH_RESULTS_MIN).max(SEARCH_RESULTS_MAX).optional(),
    maxResults: z.coerce.number().int().min(SEARCH_RESULTS_MIN).max(SEARCH_RESULTS_MAX).optional(),
    timeoutMs: z.coerce.number().int().min(TIMEOUT_MIN_MS).max(TIMEOUT_MAX_MS).optional(),
    country: z.string().trim().min(1).optional(),
    language: z.string().trim().min(1).optional(),
    freshness: RetrievalFreshnessSchema.optional(),
    includeDomains: z.array(z.string()).optional(),
    excludeDomains: z.array(z.string()).optional(),
  })
  .strict()
  .superRefine((input, ctx) => {
    if (input.limit !== undefined && input.maxResults !== undefined && input.limit !== input.maxResults) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["maxResults"],
        message: "`limit` and `maxResults` must match when both are provided",
      });
    }
  });

export const FetchControlsInputSchema = z
  .object({
    timeoutMs: z.coerce.number().int().min(TIMEOUT_MIN_MS).max(TIMEOUT_MAX_MS).optional(),
    maxAgeMs: z.coerce.number().int().min(0).max(FETCH_MAX_AGE_MAX_MS).optional(),
    fresh: z.coerce.boolean().optional(),
  })
  .strict();

export interface ResolvedSearchControls {
  maxResults: number;
  timeoutMs: number;
  country: string;
  language: string;
  freshness: z.output<typeof RetrievalFreshnessSchema>;
  domainScope: ResolvedDomainScope;
}

export interface ResolvedFetchControls {
  timeoutMs: number;
  maxAgeMs: number;
  fresh: boolean;
}

export function resolveSearchControls(input?: unknown): ResolvedSearchControls {
  const parsed = SearchControlsInputSchema.parse(input ?? {});
  const locale = LocaleSchema.parse({
    country: parsed.country,
    language: parsed.language,
  });
  const domainScope = resolveDomainScope({
    includeDomains: parsed.includeDomains,
    excludeDomains: parsed.excludeDomains,
  });

  return {
    maxResults: parsed.maxResults ?? parsed.limit ?? SEARCH_RESULTS_DEFAULT,
    timeoutMs: parsed.timeoutMs ?? TIMEOUT_DEFAULT_MS,
    country: locale.country.toUpperCase(),
    language: locale.language.toLowerCase(),
    freshness: parsed.freshness ?? "any",
    domainScope,
  };
}

export function resolveFetchControls(input?: unknown): ResolvedFetchControls {
  const parsed = FetchControlsInputSchema.parse(input ?? {});

  return {
    timeoutMs: parsed.timeoutMs ?? TIMEOUT_DEFAULT_MS,
    maxAgeMs: parsed.maxAgeMs ?? FETCH_MAX_AGE_DEFAULT_MS,
    fresh: parsed.fresh ?? false,
  };
}
