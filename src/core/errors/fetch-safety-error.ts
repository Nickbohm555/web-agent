import { type FetchFallbackReason, type FetchMetadata } from "../../sdk/contracts/fetch.js";
import {
  createEmptyFetchDecisionMetadata,
  type ComplianceDecision,
  type FetchDecisionMetadata,
  type SafetyDecision,
  type SafetyDenyDecision,
} from "../../sdk/contracts/safety.js";
import { buildCallMeta, startCallTimer, type CallMeta } from "../telemetry/call-meta.js";
import {
  createSdkError,
  type PolicyDeniedSdkError,
} from "./sdk-error.js";

export type BlockedFetchDecision =
  | SafetyDenyDecision
  | Extract<ComplianceDecision, { outcome: "deny" }>
  | Extract<ComplianceDecision, { outcome: "unavailable" }>;

export interface FetchSafetyError extends PolicyDeniedSdkError {
  readonly operation: "fetch";
  readonly stage: BlockedFetchDecision["stage"];
  readonly reason: BlockedFetchDecision["reason"];
  readonly decision: BlockedFetchDecision;
  readonly fallbackReason: FetchFallbackReason | null;
  readonly meta: CallMeta;
  readonly metadata: FetchMetadata;
}

export interface CreateFetchSafetyErrorInput {
  decision: BlockedFetchDecision;
  safetyDecision?: SafetyDecision | null;
  complianceDecision?: ComplianceDecision | null;
  startedAt?: number;
  attempts?: number;
  retries?: number;
  timings?: Record<string, number>;
  fallbackReason?: FetchFallbackReason | null;
}

export function createFetchSafetyError(
  input: CreateFetchSafetyErrorInput,
): FetchSafetyError {
  const error = createSdkError({
    kind: "policy_denied",
  }) as FetchSafetyError;
  const metadata = createFetchSafetyMetadata(
    input.decision,
    input.safetyDecision ?? null,
    input.complianceDecision ?? null,
  );

  Object.defineProperties(error, {
    code: {
      value: "POLICY_DENIED",
      enumerable: true,
      writable: false,
      configurable: false,
    },
    operation: {
      value: "fetch",
      enumerable: true,
      writable: false,
      configurable: false,
    },
    stage: {
      value: input.decision.stage,
      enumerable: true,
      writable: false,
      configurable: false,
    },
    reason: {
      value: input.decision.reason,
      enumerable: true,
      writable: false,
      configurable: false,
    },
    decision: {
      value: input.decision,
      enumerable: true,
      writable: false,
      configurable: false,
    },
    fallbackReason: {
      value: input.fallbackReason ?? null,
      enumerable: true,
      writable: false,
      configurable: false,
    },
    meta: {
      value: buildCallMeta({
        operation: "fetch",
        startedAt: input.startedAt ?? startCallTimer(),
        attempts: input.attempts ?? 1,
        retries: input.retries ?? 0,
        cacheHit: false,
        timings: input.timings ?? {},
      }),
      enumerable: true,
      writable: false,
      configurable: false,
    },
    metadata: {
      value: metadata,
      enumerable: true,
      writable: false,
      configurable: false,
    },
  });

  return error;
}

export function createFetchSafetyMetadata(
  decision: BlockedFetchDecision,
  safetyDecision: SafetyDecision | null = null,
  complianceDecision: ComplianceDecision | null = null,
): FetchMetadata {
  return {
    finalUrl: decision.target.url,
    contentType: null,
    statusCode: null,
    decisions: createFetchDecisionMetadata(decision, safetyDecision, complianceDecision),
  };
}

function createFetchDecisionMetadata(
  decision: BlockedFetchDecision,
  safetyDecision: SafetyDecision | null,
  complianceDecision: ComplianceDecision | null,
): FetchDecisionMetadata {
  if (decision.stage === "robots") {
    return {
      ...createEmptyFetchDecisionMetadata(),
      safety: safetyDecision,
      compliance: decision,
    };
  }

  return {
    ...createEmptyFetchDecisionMetadata(),
    safety: decision,
    compliance: complianceDecision,
  };
}
