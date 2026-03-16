import { type Dispatcher, type request } from "undici";

import {
  evaluateRobotsCompliance,
  type EvaluateRobotsComplianceOptions,
} from "./robots/evaluator.js";

export type RobotsPolicyState =
  | "ALLOWED"
  | "DISALLOWED"
  | "UNAVAILABLE";

type RequestLike = typeof request;

export interface EvaluateRobotsOptions {
  userAgent?: string;
  requestFn?: RequestLike;
  dispatcher?: Dispatcher;
  timeoutMs?: number;
}

export interface RobotsPolicyResult {
  state: RobotsPolicyState;
  canFetch: boolean;
  targetUrl: string;
  robotsUrl: string;
  userAgent: string;
  crawlDelaySeconds: number | null;
  reason:
    | "allowed"
    | "disallowed"
    | "missing"
    | "unreachable"
    | "invalid-robots";
}

const DEFAULT_USER_AGENT = "web-agent-bot";

export async function evaluateRobots(
  targetUrl: string,
  options: EvaluateRobotsOptions = {},
): Promise<RobotsPolicyResult> {
  const normalizedTargetUrl = new URL(targetUrl).toString();
  const userAgent = options.userAgent ?? DEFAULT_USER_AGENT;
  const result = await evaluateRobotsCompliance(normalizedTargetUrl, {
    ...(options as EvaluateRobotsComplianceOptions),
    userAgent,
    failClosedOnUnavailable: true,
  });

  return {
    state: result.outcome === "DENY" ? "DISALLOWED" : result.outcome === "UNAVAILABLE" ? "UNAVAILABLE" : "ALLOWED",
    canFetch: result.outcome !== "DENY" && result.outcome !== "UNAVAILABLE",
    targetUrl: normalizedTargetUrl,
    robotsUrl: result.reason.robotsUrl,
    userAgent,
    crawlDelaySeconds: result.crawlDelaySeconds,
    reason:
      result.outcome === "DENY"
        ? "disallowed"
        : result.reason.detail === "ROBOTS_FILE_MISSING"
          ? "missing"
          : result.outcome === "UNAVAILABLE"
            ? "unreachable"
            : result.outcome === "UNKNOWN"
              ? "invalid-robots"
              : "allowed",
  };
}
