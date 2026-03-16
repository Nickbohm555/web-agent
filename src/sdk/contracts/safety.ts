import { z } from "zod";

const SafetyDecisionStageSchema = z.enum([
  "url_preflight",
  "network_preflight",
  "redirect_preflight",
]);

export const SafetyDenyReasonSchema = z.enum([
  "UNSAFE_SCHEME",
  "URL_HAS_CREDENTIALS",
  "INVALID_HOST",
  "MALFORMED_URL",
  "SSRF_BLOCKED_IP",
  "UNSAFE_REDIRECT",
  "POLICY_DENIED",
]);

export const SafetyTargetMetadataSchema = z
  .object({
    url: z.string(),
    scheme: z.string(),
    hostname: z.string().trim().min(1).nullable(),
    port: z.number().int().min(1).max(65535).nullable(),
  })
  .strict();

export const SafetyAllowDecisionSchema = z
  .object({
    stage: SafetyDecisionStageSchema,
    outcome: z.literal("allow"),
    target: SafetyTargetMetadataSchema,
  })
  .strict();

export const SafetyDenyDecisionSchema = z
  .object({
    stage: SafetyDecisionStageSchema,
    outcome: z.literal("deny"),
    reason: SafetyDenyReasonSchema,
    target: SafetyTargetMetadataSchema,
  })
  .strict();

export const SafetyDecisionSchema = z.discriminatedUnion("outcome", [
  SafetyAllowDecisionSchema,
  SafetyDenyDecisionSchema,
]);

const ComplianceDecisionStageSchema = z.enum(["robots"]);

export const ComplianceDecisionReasonSchema = z.enum([
  "ROBOTS_ALLOW",
  "ROBOTS_DENY",
  "ROBOTS_UNKNOWN",
  "ROBOTS_UNAVAILABLE",
]);

export const ComplianceAllowDecisionSchema = z
  .object({
    stage: ComplianceDecisionStageSchema,
    outcome: z.literal("allow"),
    reason: z.literal("ROBOTS_ALLOW"),
    target: SafetyTargetMetadataSchema,
  })
  .strict();

export const ComplianceDenyDecisionSchema = z
  .object({
    stage: ComplianceDecisionStageSchema,
    outcome: z.literal("deny"),
    reason: z.literal("ROBOTS_DENY"),
    target: SafetyTargetMetadataSchema,
  })
  .strict();

export const ComplianceUnknownDecisionSchema = z
  .object({
    stage: ComplianceDecisionStageSchema,
    outcome: z.literal("unknown"),
    reason: z.literal("ROBOTS_UNKNOWN"),
    target: SafetyTargetMetadataSchema,
  })
  .strict();

export const ComplianceUnavailableDecisionSchema = z
  .object({
    stage: ComplianceDecisionStageSchema,
    outcome: z.literal("unavailable"),
    reason: z.literal("ROBOTS_UNAVAILABLE"),
    target: SafetyTargetMetadataSchema,
  })
  .strict();

export const ComplianceDecisionSchema = z.discriminatedUnion("outcome", [
  ComplianceAllowDecisionSchema,
  ComplianceDenyDecisionSchema,
  ComplianceUnknownDecisionSchema,
  ComplianceUnavailableDecisionSchema,
]);

export const FetchDecisionMetadataSchema = z
  .object({
    safety: SafetyDecisionSchema.nullable().default(null),
    compliance: ComplianceDecisionSchema.nullable().default(null),
  })
  .strict()
  .default({
    safety: null,
    compliance: null,
  });

export type SafetyDenyReason = z.output<typeof SafetyDenyReasonSchema>;
export type SafetyDecisionStage = z.output<typeof SafetyDecisionStageSchema>;
export type SafetyTargetMetadata = z.output<typeof SafetyTargetMetadataSchema>;
export type SafetyDecision = z.output<typeof SafetyDecisionSchema>;
export type ComplianceDecisionReason = z.output<typeof ComplianceDecisionReasonSchema>;
export type ComplianceDecision = z.output<typeof ComplianceDecisionSchema>;
export type FetchDecisionMetadata = z.output<typeof FetchDecisionMetadataSchema>;

export function createEmptyFetchDecisionMetadata(): FetchDecisionMetadata {
  return {
    safety: null,
    compliance: null,
  };
}
