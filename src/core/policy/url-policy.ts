import {
  SafetyDecisionSchema,
  type SafetyDecision,
  type SafetyDecisionStage,
  type SafetyDenyReason,
  type SafetyTargetMetadata,
} from "../../sdk/contracts/safety.js";

const URL_PREFLIGHT_STAGE: SafetyDecisionStage = "url_preflight";
const DEFAULT_PORT_BY_SCHEME = {
  "http:": 80,
  "https:": 443,
} as const;

export function evaluateUrlPolicy(candidateUrl: string): SafetyDecision {
  const rawCandidateUrl = candidateUrl.trim();

  if (!rawCandidateUrl) {
    return createSafetyDenyDecision(
      "MALFORMED_URL",
      createUnparsedTargetMetadata(candidateUrl),
    );
  }

  let parsedUrl: URL;

  try {
    parsedUrl = new URL(rawCandidateUrl);
  } catch {
    return createSafetyDenyDecision(
      "MALFORMED_URL",
      createUnparsedTargetMetadata(rawCandidateUrl),
    );
  }

  const target = createParsedTargetMetadata(parsedUrl);

  if (!isAllowedScheme(parsedUrl.protocol)) {
    return createSafetyDenyDecision("UNSAFE_SCHEME", target);
  }

  if (parsedUrl.username || parsedUrl.password) {
    return createSafetyDenyDecision("URL_HAS_CREDENTIALS", target);
  }

  if (!isValidHostname(parsedUrl.hostname)) {
    return createSafetyDenyDecision("INVALID_HOST", target);
  }

  return createSafetyAllowDecision(target);
}

export function normalizePreflightTarget(candidateUrl: string): SafetyTargetMetadata {
  return evaluateUrlPolicy(candidateUrl).target;
}

function createSafetyAllowDecision(target: SafetyTargetMetadata): SafetyDecision {
  return SafetyDecisionSchema.parse({
    stage: URL_PREFLIGHT_STAGE,
    outcome: "allow",
    target,
  });
}

function createSafetyDenyDecision(
  reason: SafetyDenyReason,
  target: SafetyTargetMetadata,
): SafetyDecision {
  return SafetyDecisionSchema.parse({
    stage: URL_PREFLIGHT_STAGE,
    outcome: "deny",
    reason,
    target,
  });
}

function createParsedTargetMetadata(parsedUrl: URL): SafetyTargetMetadata {
  const normalizedUrl = new URL(parsedUrl.toString());
  normalizedUrl.hash = "";

  return {
    url: normalizedUrl.toString(),
    scheme: stripProtocolSuffix(parsedUrl.protocol),
    hostname: parsedUrl.hostname.toLowerCase() || null,
    port: normalizePort(parsedUrl),
  };
}

function createUnparsedTargetMetadata(candidateUrl: string): SafetyTargetMetadata {
  return {
    url: candidateUrl,
    scheme: inferScheme(candidateUrl),
    hostname: null,
    port: null,
  };
}

function isAllowedScheme(protocol: string): protocol is keyof typeof DEFAULT_PORT_BY_SCHEME {
  return protocol === "http:" || protocol === "https:";
}

function isValidHostname(hostname: string): boolean {
  const normalizedHostname = hostname.trim();

  if (!normalizedHostname) {
    return false;
  }

  return normalizedHostname.replaceAll(".", "").length > 0;
}

function normalizePort(parsedUrl: URL): number | null {
  if (parsedUrl.port) {
    return Number(parsedUrl.port);
  }

  if (isAllowedScheme(parsedUrl.protocol)) {
    return DEFAULT_PORT_BY_SCHEME[parsedUrl.protocol];
  }

  return null;
}

function inferScheme(candidateUrl: string): string {
  const match = candidateUrl.match(/^([a-zA-Z][a-zA-Z\d+\-.]*):/);

  const scheme = match?.[1];

  if (!scheme) {
    return "";
  }

  return scheme.toLowerCase();
}

function stripProtocolSuffix(protocol: string): string {
  return protocol.endsWith(":") ? protocol.slice(0, -1).toLowerCase() : protocol.toLowerCase();
}
