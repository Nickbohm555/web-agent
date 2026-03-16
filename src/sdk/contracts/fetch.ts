import { z } from "zod";

const FETCH_TIMEOUT_DEFAULT = 10_000;
const FETCH_TIMEOUT_MIN = 1_000;
const FETCH_TIMEOUT_MAX = 30_000;

const FetchUrlSchema = z.string().trim().url();

export const FetchFallbackReasonSchema = z.enum([
  "network-error",
  "low-content-quality",
  "browser-required",
]);

const RawFetchOptionsSchema = z
  .object({
    timeoutMs: z.coerce.number().int().min(FETCH_TIMEOUT_MIN).max(FETCH_TIMEOUT_MAX).optional(),
  })
  .strict();

export const FetchOptionsSchema = RawFetchOptionsSchema.transform((input) => ({
  timeoutMs: input.timeoutMs ?? FETCH_TIMEOUT_DEFAULT,
}));

export const FetchRequestSchema = z
  .object({
    url: FetchUrlSchema.transform(normalizeUrl),
    options: RawFetchOptionsSchema.optional(),
  })
  .strict()
  .transform((input) => ({
    url: input.url,
    options: normalizeFetchOptions(input.options),
  }));

export const FetchResponseSchema = z
  .object({
    url: FetchUrlSchema.transform(normalizeUrl),
    text: z.string(),
    markdown: z.string(),
    metadata: z
      .object({
        finalUrl: FetchUrlSchema.transform(normalizeUrl),
        contentType: z.string().trim().min(1).nullable(),
        statusCode: z.number().int().min(100).max(599).nullable(),
      })
      .strict(),
    fallbackReason: FetchFallbackReasonSchema.nullable(),
  })
  .strict();

export type FetchFallbackReason = z.output<typeof FetchFallbackReasonSchema>;
export type FetchOptions = z.output<typeof FetchOptionsSchema>;
export type FetchRequest = z.output<typeof FetchRequestSchema>;
export type FetchResponse = z.output<typeof FetchResponseSchema>;

export function normalizeFetchOptions(input?: unknown): FetchOptions {
  return FetchOptionsSchema.parse(input ?? {});
}

export function normalizeFetchRequest(
  url: string,
  options?: unknown,
): FetchRequest {
  return FetchRequestSchema.parse({
    url,
    options: inputOrUndefined(options),
  });
}

export function normalizeFetchResponse(input: unknown): FetchResponse {
  return FetchResponseSchema.parse(input);
}

export function normalizeUrl(input: string): string {
  const url = new URL(input.trim());
  url.hash = "";
  return url.toString();
}

function inputOrUndefined(input: unknown): unknown {
  return input === undefined ? undefined : input;
}
