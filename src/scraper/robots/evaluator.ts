import robotsParser from "robots-parser";
import type {
  ComplianceDecision,
  ComplianceDecisionReason,
  SafetyTargetMetadata,
} from "../../sdk/contracts/safety.js";
import {
  fetchRobotsTxt,
  type FetchRobotsTxtOptions,
  type FetchRobotsTxtResult,
} from "./client.js";

const DEFAULT_USER_AGENT = "web-agent-bot";

const parseRobots = robotsParser as unknown as (
  url: string,
  contents: string,
) => {
  isAllowed: (url: string, userAgent: string) => boolean | undefined;
  getCrawlDelay: (userAgent: string) => number | undefined;
};

export type RobotsComplianceOutcome =
  | "ALLOW"
  | "DENY"
  | "UNKNOWN"
  | "UNAVAILABLE";

export interface RobotsComplianceReasonMetadata {
  code: ComplianceDecisionReason;
  detail:
    | "ROBOTS_RULE_ALLOW"
    | "ROBOTS_RULE_DENY"
    | "ROBOTS_NO_RULE_MATCH"
    | "ROBOTS_FILE_MISSING"
    | "ROBOTS_HTTP_ERROR"
    | "ROBOTS_FETCH_FAILED";
  robotsUrl: string;
  httpStatus: number | null;
  fetchedAt: string;
  errorClass: string | null;
}

export interface EvaluateRobotsComplianceOptions
  extends Omit<FetchRobotsTxtOptions, "userAgent"> {
  userAgent?: string;
  failClosedOnUnavailable?: boolean;
  fetchRobotsTxtFn?: (
    targetUrl: string,
    options?: FetchRobotsTxtOptions,
  ) => Promise<FetchRobotsTxtResult>;
}

export interface RobotsComplianceResult {
  outcome: RobotsComplianceOutcome;
  decision: ComplianceDecision;
  target: SafetyTargetMetadata;
  userAgent: string;
  crawlDelaySeconds: number | null;
  reason: RobotsComplianceReasonMetadata;
}

export async function evaluateRobotsCompliance(
  targetUrl: string,
  options: EvaluateRobotsComplianceOptions = {},
): Promise<RobotsComplianceResult> {
  const target = createTargetMetadata(targetUrl);
  const userAgent = options.userAgent ?? DEFAULT_USER_AGENT;
  const fetchRobotsTxtFn = options.fetchRobotsTxtFn ?? fetchRobotsTxt;
  const fetched = await fetchRobotsTxtFn(
    target.url,
    createFetchRobotsOptions(options, userAgent),
  );

  if (fetched.state === "MISSING") {
    return {
      outcome: "ALLOW",
      decision: createDecision("allow", "ROBOTS_ALLOW", target),
      target,
      userAgent,
      crawlDelaySeconds: null,
      reason: createReasonMetadata("ROBOTS_ALLOW", "ROBOTS_FILE_MISSING", fetched),
    };
  }

  if (fetched.state === "UNAVAILABLE") {
    if (options.failClosedOnUnavailable ?? true) {
      return {
        outcome: "UNAVAILABLE",
        decision: createDecision("unavailable", "ROBOTS_UNAVAILABLE", target),
        target,
        userAgent,
        crawlDelaySeconds: null,
        reason: createReasonMetadata("ROBOTS_UNAVAILABLE", "ROBOTS_FETCH_FAILED", fetched),
      };
    }

    return {
      outcome: "UNKNOWN",
      decision: createDecision("unknown", "ROBOTS_UNKNOWN", target),
      target,
      userAgent,
      crawlDelaySeconds: null,
      reason: createReasonMetadata("ROBOTS_UNKNOWN", "ROBOTS_FETCH_FAILED", fetched),
    };
  }

  const parsedRobots = parseRobots(fetched.robotsUrl, fetched.body);
  const allowed = parsedRobots.isAllowed(target.url, userAgent);
  const crawlDelaySeconds = toNumberOrNull(parsedRobots.getCrawlDelay(userAgent));

  if (allowed === false) {
    return {
      outcome: "DENY",
      decision: createDecision("deny", "ROBOTS_DENY", target),
      target,
      userAgent,
      crawlDelaySeconds,
      reason: createReasonMetadata("ROBOTS_DENY", "ROBOTS_RULE_DENY", fetched),
    };
  }

  if (allowed === true) {
    return {
      outcome: "ALLOW",
      decision: createDecision("allow", "ROBOTS_ALLOW", target),
      target,
      userAgent,
      crawlDelaySeconds,
      reason: createReasonMetadata("ROBOTS_ALLOW", "ROBOTS_RULE_ALLOW", fetched),
    };
  }

  return {
    outcome: "UNKNOWN",
    decision: createDecision("unknown", "ROBOTS_UNKNOWN", target),
    target,
    userAgent,
    crawlDelaySeconds,
    reason: createReasonMetadata("ROBOTS_UNKNOWN", "ROBOTS_NO_RULE_MATCH", fetched),
  };
}

function createDecision(
  outcome: "allow",
  reason: "ROBOTS_ALLOW",
  target: SafetyTargetMetadata,
): ComplianceDecision;
function createDecision(
  outcome: "deny",
  reason: "ROBOTS_DENY",
  target: SafetyTargetMetadata,
): ComplianceDecision;
function createDecision(
  outcome: "unknown",
  reason: "ROBOTS_UNKNOWN",
  target: SafetyTargetMetadata,
): ComplianceDecision;
function createDecision(
  outcome: "unavailable",
  reason: "ROBOTS_UNAVAILABLE",
  target: SafetyTargetMetadata,
): ComplianceDecision;
function createDecision(
  outcome: ComplianceDecision["outcome"],
  reason: ComplianceDecisionReason,
  target: SafetyTargetMetadata,
): ComplianceDecision {
  if (outcome === "allow" && reason === "ROBOTS_ALLOW") {
    return { stage: "robots", outcome, reason, target };
  }

  if (outcome === "deny" && reason === "ROBOTS_DENY") {
    return { stage: "robots", outcome, reason, target };
  }

  if (outcome === "unknown" && reason === "ROBOTS_UNKNOWN") {
    return { stage: "robots", outcome, reason, target };
  }

  return { stage: "robots", outcome: "unavailable", reason: "ROBOTS_UNAVAILABLE", target };
}

function createReasonMetadata(
  code: ComplianceDecisionReason,
  detail: RobotsComplianceReasonMetadata["detail"],
  fetched: FetchRobotsTxtResult,
): RobotsComplianceReasonMetadata {
  return {
    code,
    detail,
    robotsUrl: fetched.robotsUrl,
    httpStatus: fetched.statusCode,
    fetchedAt: fetched.fetchedAt,
    errorClass: fetched.state === "UNAVAILABLE" ? fetched.errorClass : null,
  };
}

function createFetchRobotsOptions(
  options: EvaluateRobotsComplianceOptions,
  userAgent: string,
): FetchRobotsTxtOptions {
  return {
    ...(options.requestFn ? { requestFn: options.requestFn } : {}),
    ...(options.dispatcher ? { dispatcher: options.dispatcher } : {}),
    ...(options.timeoutMs !== undefined ? { timeoutMs: options.timeoutMs } : {}),
    userAgent,
  };
}

function createTargetMetadata(targetUrl: string): SafetyTargetMetadata {
  const normalizedUrl = new URL(targetUrl);

  return {
    url: normalizedUrl.toString(),
    scheme: normalizedUrl.protocol.slice(0, -1),
    hostname: normalizedUrl.hostname || null,
    port: normalizedUrl.port === ""
      ? normalizedUrl.protocol === "https:"
        ? 443
        : 80
      : Number.parseInt(normalizedUrl.port, 10),
  };
}

function toNumberOrNull(value: number | undefined): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}
