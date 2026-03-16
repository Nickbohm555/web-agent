import { performance } from "node:perf_hooks";

import { z } from "zod";

export const CallOperationSchema = z.enum(["search", "fetch"]);

export const CallMetaUsageValueSchema = z.union([
  z.number().nonnegative(),
  z.string(),
  z.boolean(),
]);

export const CallMetaSchema = z
  .object({
    operation: CallOperationSchema,
    durationMs: z.number().nonnegative(),
    attempts: z.number().int().positive(),
    retries: z.number().int().nonnegative(),
    cacheHit: z.boolean(),
    timings: z.record(z.string(), z.number().nonnegative()),
    usage: z
      .record(z.string(), z.record(z.string(), CallMetaUsageValueSchema))
      .optional(),
  })
  .strict();

export type CallOperation = z.output<typeof CallOperationSchema>;
export type CallMeta = z.output<typeof CallMetaSchema>;
export type CallMetaUsage = NonNullable<CallMeta["usage"]>;

export interface BuildCallMetaInput {
  operation: CallOperation;
  startedAt: number;
  endedAt?: number;
  attempts: number;
  retries: number;
  cacheHit: boolean;
  timings?: Record<string, number>;
  usage?: CallMetaUsage;
}

export function startCallTimer(): number {
  return performance.now();
}

export function measureDurationMs(
  startedAt: number,
  endedAt: number = performance.now(),
): number {
  return normalizeDuration(endedAt - startedAt);
}

export function buildCallMeta(input: BuildCallMetaInput): CallMeta {
  const durationMs = measureDurationMs(input.startedAt, input.endedAt);

  return CallMetaSchema.parse({
    operation: input.operation,
    durationMs,
    attempts: input.attempts,
    retries: input.retries,
    cacheHit: input.cacheHit,
    timings: normalizeTimings(input.timings),
    ...(input.usage ? { usage: input.usage } : {}),
  });
}

function normalizeDuration(value: number): number {
  if (!Number.isFinite(value) || value < 0) {
    return 0;
  }

  return Number(value.toFixed(3));
}

function normalizeTimings(
  timings: Record<string, number> | undefined,
): Record<string, number> {
  if (!timings) {
    return {};
  }

  return Object.fromEntries(
    Object.entries(timings).map(([key, value]) => [key, normalizeDuration(value)]),
  );
}
