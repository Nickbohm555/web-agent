export const SDK_ERROR_KINDS = [
  "rate_limited",
  "timeout",
  "network",
  "provider_unavailable",
  "invalid_request",
  "policy_denied",
  "content_unavailable",
  "unknown",
] as const;

export type SdkErrorKind = (typeof SDK_ERROR_KINDS)[number];

interface SdkErrorBase<K extends SdkErrorKind, R extends boolean> extends Error {
  readonly name: "SdkError";
  readonly kind: K;
  readonly retryable: R;
  readonly statusCode?: number;
  readonly retryAfterMs?: number;
  readonly cause?: unknown;
}

export type RateLimitedSdkError = SdkErrorBase<"rate_limited", true>;
export type TimeoutSdkError = SdkErrorBase<"timeout", true>;
export type NetworkSdkError = SdkErrorBase<"network", true>;
export type ProviderUnavailableSdkError = SdkErrorBase<"provider_unavailable", true>;
export type InvalidRequestSdkError = SdkErrorBase<"invalid_request", false>;
export type PolicyDeniedSdkError = SdkErrorBase<"policy_denied", false>;
export type ContentUnavailableSdkError = SdkErrorBase<"content_unavailable", false>;
export type UnknownSdkError = SdkErrorBase<"unknown", false>;

export type SdkError =
  | RateLimitedSdkError
  | TimeoutSdkError
  | NetworkSdkError
  | ProviderUnavailableSdkError
  | InvalidRequestSdkError
  | PolicyDeniedSdkError
  | ContentUnavailableSdkError
  | UnknownSdkError;

const SDK_ERROR_MESSAGES: Record<SdkErrorKind, string> = {
  rate_limited: "Request was rate limited.",
  timeout: "Request timed out.",
  network: "Network request failed.",
  provider_unavailable: "Provider is temporarily unavailable.",
  invalid_request: "Request is invalid.",
  policy_denied: "Request was denied by policy.",
  content_unavailable: "Requested content is unavailable.",
  unknown: "Unexpected SDK error.",
};

const RETRYABLE_KINDS = new Set<SdkErrorKind>([
  "rate_limited",
  "timeout",
  "network",
  "provider_unavailable",
]);

export interface CreateSdkErrorInput {
  kind: SdkErrorKind;
  message?: string;
  statusCode?: number;
  retryAfterMs?: number;
  cause?: unknown;
}

export function createSdkError(input: CreateSdkErrorInput): SdkError {
  const error = new Error(input.message ?? SDK_ERROR_MESSAGES[input.kind]) as SdkError;

  Object.defineProperties(error, {
    name: {
      value: "SdkError",
      enumerable: false,
      writable: true,
      configurable: true,
    },
    kind: {
      value: input.kind,
      enumerable: true,
      writable: false,
      configurable: false,
    },
    retryable: {
      value: RETRYABLE_KINDS.has(input.kind),
      enumerable: true,
      writable: false,
      configurable: false,
    },
    statusCode: {
      value: input.statusCode,
      enumerable: input.statusCode !== undefined,
      writable: false,
      configurable: false,
    },
    retryAfterMs: {
      value: input.retryAfterMs,
      enumerable: input.retryAfterMs !== undefined,
      writable: false,
      configurable: false,
    },
    cause: {
      value: input.cause,
      enumerable: false,
      writable: false,
      configurable: false,
    },
  });

  return error;
}

export function isSdkError(value: unknown): value is SdkError {
  if (!(value instanceof Error)) {
    return false;
  }

  if (value.name !== "SdkError") {
    return false;
  }

  const kind = "kind" in value ? value.kind : undefined;
  const retryable = "retryable" in value ? value.retryable : undefined;
  const statusCode = "statusCode" in value ? value.statusCode : undefined;
  const retryAfterMs = "retryAfterMs" in value ? value.retryAfterMs : undefined;

  return (
    typeof kind === "string" &&
    SDK_ERROR_KINDS.includes(kind as SdkErrorKind) &&
    typeof retryable === "boolean" &&
    (statusCode === undefined || typeof statusCode === "number") &&
    (retryAfterMs === undefined || typeof retryAfterMs === "number")
  );
}
