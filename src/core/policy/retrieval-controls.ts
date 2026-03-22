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

export const RunRetrievalPolicyInputSchema = z
  .object({
    country: z.string().trim().min(1).optional(),
    language: z.string().trim().min(1).optional(),
    freshness: RetrievalFreshnessSchema.optional(),
    includeDomains: z.array(z.string()).optional(),
    excludeDomains: z.array(z.string()).optional(),
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

export interface ResolvedRunRetrievalPolicy {
  search: Pick<
    ResolvedSearchControls,
    "country" | "language" | "freshness" | "domainScope"
  >;
  fetch: Pick<ResolvedFetchControls, "maxAgeMs" | "fresh">;
}

type RetrievalFreshness = z.output<typeof RetrievalFreshnessSchema>;

const ResolvedRunRetrievalPolicySchema = z.object({
  search: z.object({
    country: z.string().trim().min(1),
    language: z.string().trim().min(1),
    freshness: RetrievalFreshnessSchema,
    domainScope: z.object({
      includeDomains: z.array(z.string()).default([]),
      excludeDomains: z.array(z.string()).default([]),
    }).strict(),
  }).strict(),
  fetch: z.object({
    maxAgeMs: z.coerce.number().int().min(0).max(FETCH_MAX_AGE_MAX_MS),
    fresh: z.coerce.boolean(),
  }).strict(),
}).strict();

const PROMPT_DOMAIN_HINTS = [
  { pattern: /\bopenai\b/i, domains: ["openai.com", "platform.openai.com"] },
  { pattern: /\breact\b/i, domains: ["react.dev"] },
  { pattern: /\bnext(?:\.js|js)?\b/i, domains: ["nextjs.org", "vercel.com"] },
  { pattern: /\bvercel\b/i, domains: ["vercel.com"] },
  { pattern: /\bnode(?:\.js|js)?\b/i, domains: ["nodejs.org"] },
  { pattern: /\bpython\b/i, domains: ["docs.python.org", "python.org"] },
  { pattern: /\bfastapi\b/i, domains: ["fastapi.tiangolo.com"] },
  { pattern: /\bdocker\b/i, domains: ["docs.docker.com", "docker.com"] },
  { pattern: /\bstripe\b/i, domains: ["docs.stripe.com", "stripe.com"] },
  { pattern: /\baws\b|amazon web services/i, domains: ["docs.aws.amazon.com", "aws.amazon.com"] },
  { pattern: /\btailwind(?:css)?\b/i, domains: ["tailwindcss.com"] },
] as const;

const OFFICIAL_SOURCE_PATTERN =
  /\b(official docs?(?: only)?|official documentation|official source(?:s)?|official site|primary source(?:s)?|company filing|regulatory filing|sec filing)\b/i;
const SEC_FILING_PATTERN =
  /\b(sec filing|10-k|10-q|8-k|annual report|quarterly report|earnings filing)\b/i;
const TODAY_PATTERN =
  /\b(today|breaking|just announced|just released|as of today|newly announced)\b/i;
const WEEK_PATTERN =
  /\b(this week|past week|last week|recent|recent coverage|latest|most recent|newest|current)\b/i;
const MONTH_PATTERN = /\b(this month|past month|last month)\b/i;
const YEAR_PATTERN = /\b(this year|past year|last year)\b/i;
const DOMAIN_PATTERN = /\b(?:[a-z0-9-]+\.)+[a-z]{2,}\b/gi;
const FETCH_MAX_AGE_BY_FRESHNESS: Record<RetrievalFreshness, number> = {
  any: FETCH_MAX_AGE_DEFAULT_MS,
  day: 60 * 60 * 1000,
  week: 6 * 60 * 60 * 1000,
  month: 24 * 60 * 60 * 1000,
  year: 24 * 60 * 60 * 1000,
};

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

export function resolveRunRetrievalPolicy(
  input?: unknown,
  prompt?: string,
): ResolvedRunRetrievalPolicy {
  const resolvedInput = ResolvedRunRetrievalPolicySchema.safeParse(input);
  if (resolvedInput.success) {
    return normalizeResolvedRunRetrievalPolicy(resolvedInput.data);
  }

  const inferred = inferRunRetrievalPolicy(prompt);
  const parsed = RunRetrievalPolicyInputSchema.parse(input ?? {});
  const search = resolveSearchControls({
    country: parsed.country ?? inferred.search.country,
    language: parsed.language ?? inferred.search.language,
    freshness: parsed.freshness ?? inferred.search.freshness,
    includeDomains: parsed.includeDomains ?? inferred.search.domainScope.includeDomains,
    excludeDomains: parsed.excludeDomains ?? inferred.search.domainScope.excludeDomains,
  });
  const fetch = resolveFetchControls({
    maxAgeMs: parsed.maxAgeMs ?? inferred.fetch.maxAgeMs,
    fresh: parsed.fresh ?? inferred.fetch.fresh,
  });

  return {
    search: {
      country: search.country,
      language: search.language,
      freshness: search.freshness,
      domainScope: search.domainScope,
    },
    fetch: {
      maxAgeMs: fetch.maxAgeMs,
      fresh: fetch.fresh,
    },
  };
}

export function inferRunRetrievalPolicy(prompt?: string): ResolvedRunRetrievalPolicy {
  const normalizedPrompt = prompt?.trim() ?? "";
  const inferredFreshness = inferPromptFreshness(normalizedPrompt);
  const inferredDomains = inferPromptIncludeDomains(normalizedPrompt);

  return {
    search: {
      country: "US",
      language: "en",
      freshness: inferredFreshness,
      domainScope: {
        includeDomains: inferredDomains,
        excludeDomains: [],
      },
    },
    fetch: {
      maxAgeMs: FETCH_MAX_AGE_BY_FRESHNESS[inferredFreshness],
      fresh: inferredFreshness !== "any",
    },
  };
}

function normalizeResolvedRunRetrievalPolicy(
  policy: z.output<typeof ResolvedRunRetrievalPolicySchema>,
): ResolvedRunRetrievalPolicy {
  return {
    search: {
      country: policy.search.country.toUpperCase(),
      language: policy.search.language.toLowerCase(),
      freshness: policy.search.freshness,
      domainScope: resolveDomainScope(policy.search.domainScope),
    },
    fetch: {
      maxAgeMs: policy.fetch.maxAgeMs,
      fresh: policy.fetch.fresh,
    },
  };
}

function inferPromptFreshness(
  prompt: string,
): RetrievalFreshness {
  if (!prompt) {
    return "any";
  }

  if (TODAY_PATTERN.test(prompt)) {
    return "day";
  }
  if (MONTH_PATTERN.test(prompt) || SEC_FILING_PATTERN.test(prompt)) {
    return "month";
  }
  if (YEAR_PATTERN.test(prompt)) {
    return "year";
  }
  if (WEEK_PATTERN.test(prompt)) {
    return "week";
  }
  return "any";
}

function inferPromptIncludeDomains(prompt: string): string[] {
  if (!prompt) {
    return [];
  }

  const explicitDomains = Array.from(prompt.matchAll(DOMAIN_PATTERN), (match) => match[0]);
  const hintedDomains = PROMPT_DOMAIN_HINTS.flatMap((hint) =>
    hint.pattern.test(prompt) ? hint.domains : [],
  );
  const hasSecFilingHint = SEC_FILING_PATTERN.test(prompt);
  const shouldScopeToOfficialSources =
    OFFICIAL_SOURCE_PATTERN.test(prompt) || hasSecFilingHint;

  if (!shouldScopeToOfficialSources && explicitDomains.length === 0) {
    return [];
  }

  const domains = hasSecFilingHint
    ? ["sec.gov", ...explicitDomains, ...hintedDomains]
    : [...explicitDomains, ...hintedDomains];

  return resolveDomainScope({ includeDomains: domains }).includeDomains;
}

export function mergeRunPolicyIntoSearchControls(
  policy?: unknown,
  input?: unknown,
): ResolvedSearchControls {
  const resolvedPolicy = resolveRunRetrievalPolicy(policy);
  const parsedInput = SearchControlsInputSchema.parse(input ?? {});

  return resolveSearchControls({
    ...parsedInput,
    country: parsedInput.country ?? resolvedPolicy.search.country,
    language: parsedInput.language ?? resolvedPolicy.search.language,
    freshness: parsedInput.freshness ?? resolvedPolicy.search.freshness,
    includeDomains:
      parsedInput.includeDomains ?? resolvedPolicy.search.domainScope.includeDomains,
    excludeDomains:
      parsedInput.excludeDomains ?? resolvedPolicy.search.domainScope.excludeDomains,
  });
}

export function mergeRunPolicyIntoFetchControls(
  policy?: unknown,
  input?: unknown,
): ResolvedFetchControls {
  const resolvedPolicy = resolveRunRetrievalPolicy(policy);
  const parsedInput = FetchControlsInputSchema.parse(input ?? {});

  return resolveFetchControls({
    ...parsedInput,
    maxAgeMs: parsedInput.maxAgeMs ?? resolvedPolicy.fetch.maxAgeMs,
    fresh: parsedInput.fresh ?? resolvedPolicy.fetch.fresh,
  });
}

export function mergeRunPolicyIntoSearchInput(
  policy?: unknown,
  input?: unknown,
): z.input<typeof SearchControlsInputSchema> {
  const merged = mergeRunPolicyIntoSearchControls(policy, input);

  return SearchControlsInputSchema.parse({
    ...(SearchControlsInputSchema.parse(input ?? {})),
    country: merged.country,
    language: merged.language,
    freshness: merged.freshness,
    includeDomains: merged.domainScope.includeDomains,
    excludeDomains: merged.domainScope.excludeDomains,
  });
}

export function mergeRunPolicyIntoFetchInput(
  policy?: unknown,
  input?: unknown,
): z.input<typeof FetchControlsInputSchema> {
  const merged = mergeRunPolicyIntoFetchControls(policy, input);

  return FetchControlsInputSchema.parse({
    ...(FetchControlsInputSchema.parse(input ?? {})),
    maxAgeMs: merged.maxAgeMs,
    fresh: merged.fresh,
  });
}
