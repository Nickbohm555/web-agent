import pRetry, { AbortError, type Options as PRetryOptions } from "p-retry";

import { mapError } from "../errors/map-error.js";
import type { SdkError } from "../errors/sdk-error.js";

export interface RetryPolicy {
  retries?: number;
  minTimeoutMs?: number;
  maxTimeoutMs?: number;
  maxRetryTimeMs?: number;
  factor?: number;
  sleep?: (delayMs: number) => Promise<void>;
}

export interface RetryContext {
  attemptNumber: number;
  retriesConsumed: number;
}

export interface RetryResult<T> {
  value: T;
  attempts: number;
  retries: number;
}

interface ResolvedRetryPolicy {
  retries: number;
  minTimeoutMs: number;
  maxTimeoutMs: number;
  maxRetryTimeMs: number;
  factor: number;
  sleep: (delayMs: number) => Promise<void>;
}

const DEFAULT_RETRY_POLICY: ResolvedRetryPolicy = {
  retries: 2,
  minTimeoutMs: 250,
  maxTimeoutMs: 1_000,
  maxRetryTimeMs: 5_000,
  factor: 2,
  sleep: defaultSleep,
};

export async function executeWithRetry<T>(
  operation: (context: RetryContext) => Promise<T>,
  policy: RetryPolicy = {},
): Promise<RetryResult<T>> {
  const resolvedPolicy = resolveRetryPolicy(policy);
  let attempts = 0;

  try {
    const value = await pRetry(
      async () => {
        attempts += 1;

        try {
          return await operation({
            attemptNumber: attempts,
            retriesConsumed: Math.max(0, attempts - 1),
          });
        } catch (error) {
          const sdkError = mapError(error);

          if (!sdkError.retryable) {
            throw withAttemptNumber(new AbortError(sdkError), attempts);
          }

          throw withAttemptNumber(sdkError, attempts);
        }
      },
      toPRetryOptions(resolvedPolicy),
    );

    return {
      value,
      attempts,
      retries: Math.max(0, attempts - 1),
    };
  } catch (error) {
    throw withAttemptNumber(error, attempts);
  }
}

function toPRetryOptions(policy: ResolvedRetryPolicy): PRetryOptions {
  return {
    retries: policy.retries,
    factor: policy.factor,
    minTimeout: 0,
    maxTimeout: 0,
    maxRetryTime: policy.maxRetryTimeMs,
    randomize: false,
    shouldRetry: ({ error }) => {
      const sdkError = mapError(error);
      return sdkError.retryable;
    },
    onFailedAttempt: async (context) => {
      if (context.retriesLeft === 0) {
        return;
      }

      const sdkError = mapError(context.error);
      const delayMs = getRetryDelayMs(sdkError, context.attemptNumber, policy);

      if (delayMs > 0) {
        await policy.sleep(delayMs);
      }
    },
  };
}

function getRetryDelayMs(
  error: SdkError,
  attemptNumber: number,
  policy: ResolvedRetryPolicy,
): number {
  if (error.retryAfterMs !== undefined) {
    return error.retryAfterMs;
  }

  const exponentialDelay = policy.minTimeoutMs * Math.pow(policy.factor, Math.max(0, attemptNumber - 1));
  return Math.min(policy.maxTimeoutMs, exponentialDelay);
}

function resolveRetryPolicy(policy: RetryPolicy): ResolvedRetryPolicy {
  return {
    retries: policy.retries ?? DEFAULT_RETRY_POLICY.retries,
    minTimeoutMs: policy.minTimeoutMs ?? DEFAULT_RETRY_POLICY.minTimeoutMs,
    maxTimeoutMs: policy.maxTimeoutMs ?? DEFAULT_RETRY_POLICY.maxTimeoutMs,
    maxRetryTimeMs: policy.maxRetryTimeMs ?? DEFAULT_RETRY_POLICY.maxRetryTimeMs,
    factor: policy.factor ?? DEFAULT_RETRY_POLICY.factor,
    sleep: policy.sleep ?? DEFAULT_RETRY_POLICY.sleep,
  };
}

function withAttemptNumber<T>(error: T, attempts: number): T {
  if (!(error instanceof Error)) {
    return error;
  }

  Object.defineProperty(error, "attemptNumber", {
    value: attempts,
    enumerable: false,
    writable: true,
    configurable: true,
  });

  return error;
}

async function defaultSleep(delayMs: number): Promise<void> {
  await new Promise((resolve) => {
    setTimeout(resolve, delayMs);
  });
}
