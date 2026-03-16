import pRetry, { AbortError, type Options as PRetryOptions } from "p-retry";

export type RetryDecision =
  | {
      retryable: true;
      reason: string;
    }
  | {
      retryable: false;
      reason: string;
    };

export interface RetryPolicy {
  retries?: number;
  minTimeoutMs?: number;
  maxTimeoutMs?: number;
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

const DEFAULT_RETRY_POLICY = {
  retries: 2,
  minTimeoutMs: 250,
  maxTimeoutMs: 1_000,
} satisfies Required<RetryPolicy>;

export async function executeWithRetry<T>(
  operation: (context: RetryContext) => Promise<T>,
  shouldRetry: (error: unknown) => RetryDecision,
  policy: RetryPolicy = {},
): Promise<RetryResult<T>> {
  let attempts = 0;

  const value = await pRetry(
    async () => {
      attempts += 1;

      try {
        return await operation({
          attemptNumber: attempts,
          retriesConsumed: Math.max(0, attempts - 1),
        });
      } catch (error) {
        const decision = shouldRetry(error);

        if (!decision.retryable) {
          throw new AbortError(error instanceof Error ? error : new Error(decision.reason));
        }

        throw error;
      }
    },
    toPRetryOptions(policy),
  );

  return {
    value,
    attempts,
    retries: Math.max(0, attempts - 1),
  };
}

function toPRetryOptions(policy: RetryPolicy): PRetryOptions {
  return {
    retries: policy.retries ?? DEFAULT_RETRY_POLICY.retries,
    minTimeout: policy.minTimeoutMs ?? DEFAULT_RETRY_POLICY.minTimeoutMs,
    maxTimeout: policy.maxTimeoutMs ?? DEFAULT_RETRY_POLICY.maxTimeoutMs,
    factor: 2,
    randomize: false,
  };
}
