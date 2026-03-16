import { z } from "zod";
import { CallMetaSchema } from "../../core/telemetry/call-meta.js";
import {
  FetchControlsInputSchema,
  resolveFetchControls,
  type ResolvedFetchControls,
} from "../../core/policy/retrieval-controls.js";
import { FetchDecisionMetadataSchema } from "./safety.js";

const FetchUrlSchema = z.string().trim().url();

export const FetchFallbackReasonSchema = z.enum([
  "network-error",
  "low-content-quality",
  "browser-required",
]);

export const FetchCacheControlInputSchema = FetchControlsInputSchema.pick({
  maxAgeMs: true,
  fresh: true,
});

export const FetchOptionsSchema = FetchControlsInputSchema.transform((input) =>
  resolveFetchControls(input),
);

export const FetchRequestSchema = z
  .object({
    url: FetchUrlSchema.transform(normalizeUrl),
    options: FetchControlsInputSchema.optional(),
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
    meta: CallMetaSchema,
    metadata: z
      .object({
        finalUrl: FetchUrlSchema.transform(normalizeUrl),
        contentType: z.string().trim().min(1).nullable(),
        statusCode: z.number().int().min(100).max(599).nullable(),
        decisions: FetchDecisionMetadataSchema,
      })
      .strict(),
    fallbackReason: FetchFallbackReasonSchema.nullable(),
  })
  .strict();

export type FetchFallbackReason = z.output<typeof FetchFallbackReasonSchema>;
export type FetchOptions = z.input<typeof FetchOptionsSchema>;
export type NormalizedFetchOptions = ResolvedFetchControls;
export type FetchCacheControlInput = z.input<typeof FetchCacheControlInputSchema>;
export type NormalizedFetchCacheControl = Pick<
  ResolvedFetchControls,
  "maxAgeMs" | "fresh"
>;
export type FetchRequest = z.output<typeof FetchRequestSchema>;
export type FetchMetadata = z.output<typeof FetchResponseSchema.shape.metadata>;
export type FetchResponse = z.output<typeof FetchResponseSchema>;

export function normalizeFetchOptions(input?: unknown): NormalizedFetchOptions {
  return FetchOptionsSchema.parse(input ?? {});
}

export function normalizeFetchCacheControl(
  input?: unknown,
): NormalizedFetchCacheControl {
  const options = normalizeFetchOptions(input);

  return {
    maxAgeMs: options.maxAgeMs,
    fresh: options.fresh,
  };
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
