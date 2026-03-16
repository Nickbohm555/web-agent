import { isIP } from "node:net";
import { lookup } from "node:dns/promises";

import {
  evaluateIpAddressPolicy,
  type IpAddressPolicyDecision,
  type IpAddressSafetyClass,
} from "./ip-policy.js";
import {
  SafetyAllowDecisionSchema,
  SafetyDenyDecisionSchema,
  type SafetyAllowDecision,
  type SafetyDenyDecision,
  type SafetyTargetMetadata,
} from "../../sdk/contracts/safety.js";

const NETWORK_PREFLIGHT_STAGE = "network_preflight";

export interface ResolvedAddressCandidate {
  address: string;
  family: 4 | 6;
  normalized: string;
  classification: IpAddressSafetyClass;
  outcome: IpAddressPolicyDecision["outcome"];
}

export interface ResolveAndClassifyAllowResult {
  outcome: "allow";
  decision: SafetyAllowDecision;
  resolvedAddresses: ResolvedAddressCandidate[];
}

export interface ResolveAndClassifyDenyResult {
  outcome: "deny";
  decision: SafetyDenyDecision;
  resolvedAddresses: ResolvedAddressCandidate[];
  resolverErrorCode: string | null;
}

export type ResolveAndClassifyResult =
  | ResolveAndClassifyAllowResult
  | ResolveAndClassifyDenyResult;

interface LookupAddress {
  address: string;
  family: 4 | 6;
}

type LookupFn = (
  hostname: string,
  options: {
    all: true;
    verbatim: true;
  },
) => Promise<LookupAddress[]>;

export interface ResolveAndClassifyOptions {
  lookupFn?: LookupFn;
}

export async function resolveAndClassifyTarget(
  target: SafetyTargetMetadata,
  options: ResolveAndClassifyOptions = {},
): Promise<ResolveAndClassifyResult> {
  if (!target.hostname) {
    return createDenyResult(target, "INVALID_HOST", [], null);
  }

  const directIpFamily = isIP(target.hostname);

  if (directIpFamily === 4 || directIpFamily === 6) {
    const resolvedAddresses = [createResolvedAddressCandidate(target.hostname, directIpFamily)];
    const deniedAddress = resolvedAddresses.find((candidate) => candidate.outcome === "deny");

    if (deniedAddress) {
      return createDenyResult(target, "SSRF_BLOCKED_IP", resolvedAddresses, null);
    }

    return createAllowResult(target, resolvedAddresses);
  }

  const lookupFn: LookupFn =
    options.lookupFn ??
    ((hostname, lookupOptions) => lookup(hostname, lookupOptions) as Promise<LookupAddress[]>);

  try {
    const lookupResults = await lookupFn(target.hostname, {
      all: true,
      verbatim: true,
    });

    if (lookupResults.length === 0) {
      return createDenyResult(target, "DNS_RESOLUTION_FAILED", [], null);
    }

    const resolvedAddresses = normalizeResolvedAddresses(lookupResults);
    const deniedAddress = resolvedAddresses.find((candidate) => candidate.outcome === "deny");

    if (deniedAddress) {
      return createDenyResult(target, "SSRF_BLOCKED_IP", resolvedAddresses, null);
    }

    return createAllowResult(target, resolvedAddresses);
  } catch (error) {
    return createDenyResult(
      target,
      "DNS_RESOLUTION_FAILED",
      [],
      readResolverErrorCode(error),
    );
  }
}

function normalizeResolvedAddresses(results: LookupAddress[]): ResolvedAddressCandidate[] {
  const deduped = new Map<string, ResolvedAddressCandidate>();

  for (const result of results) {
    const candidate = createResolvedAddressCandidate(result.address, result.family);
    deduped.set(`${candidate.family}:${candidate.normalized}`, candidate);
  }

  return [...deduped.values()].sort(compareResolvedAddressCandidates);
}

function createResolvedAddressCandidate(
  address: string,
  family: number,
): ResolvedAddressCandidate {
  const policyDecision = evaluateIpAddressPolicy(address);

  return {
    address,
    family: family === 6 ? 6 : 4,
    normalized: policyDecision.metadata.normalized,
    classification: policyDecision.metadata.classification,
    outcome: policyDecision.outcome,
  };
}

function compareResolvedAddressCandidates(
  left: ResolvedAddressCandidate,
  right: ResolvedAddressCandidate,
): number {
  if (left.family !== right.family) {
    return left.family - right.family;
  }

  return left.normalized.localeCompare(right.normalized);
}

function createAllowResult(
  target: SafetyTargetMetadata,
  resolvedAddresses: ResolvedAddressCandidate[],
): ResolveAndClassifyAllowResult {
  return {
    outcome: "allow",
    decision: SafetyAllowDecisionSchema.parse({
      stage: NETWORK_PREFLIGHT_STAGE,
      outcome: "allow",
      target,
    }),
    resolvedAddresses,
  };
}

function createDenyResult(
  target: SafetyTargetMetadata,
  reason: SafetyDenyDecision["reason"],
  resolvedAddresses: ResolvedAddressCandidate[],
  resolverErrorCode: string | null,
): ResolveAndClassifyDenyResult {
  return {
    outcome: "deny",
    decision: SafetyDenyDecisionSchema.parse({
      stage: NETWORK_PREFLIGHT_STAGE,
      outcome: "deny",
      reason,
      target,
    }),
    resolvedAddresses,
    resolverErrorCode,
  };
}

function readResolverErrorCode(error: unknown): string | null {
  if (!(error instanceof Error) || !("code" in error)) {
    return null;
  }

  const code = error.code;

  return typeof code === "string" && code.trim() ? code : null;
}
