import pino from "pino";
import robotsParser from "robots-parser";
import { request, type Dispatcher } from "undici";

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
const DEFAULT_TIMEOUT_MS = 5_000;
const logger = pino({ level: process.env.LOG_LEVEL ?? "silent" });
const parseRobots = robotsParser as unknown as (
  url: string,
  contents: string,
) => {
  isAllowed: (url: string, userAgent: string) => boolean | undefined;
  getCrawlDelay: (userAgent: string) => number | undefined;
};

export async function evaluateRobots(
  targetUrl: string,
  options: EvaluateRobotsOptions = {},
): Promise<RobotsPolicyResult> {
  const normalizedTargetUrl = new URL(targetUrl).toString();
  const robotsUrl = new URL("/robots.txt", normalizedTargetUrl).toString();
  const userAgent = options.userAgent ?? DEFAULT_USER_AGENT;
  const requestFn = options.requestFn ?? request;

  const startedAt = Date.now();

  try {
    const response = await requestFn(robotsUrl, {
      method: "GET",
      headers: {
        "user-agent": userAgent,
      },
      headersTimeout: options.timeoutMs ?? DEFAULT_TIMEOUT_MS,
      bodyTimeout: options.timeoutMs ?? DEFAULT_TIMEOUT_MS,
      ...(options.dispatcher ? { dispatcher: options.dispatcher } : {}),
    });

    if (response.statusCode === 404) {
      return logResult({
        state: "ALLOWED",
        canFetch: true,
        targetUrl: normalizedTargetUrl,
        robotsUrl,
        userAgent,
        crawlDelaySeconds: null,
        reason: "missing",
      }, startedAt);
    }

    if (response.statusCode >= 400) {
      return logResult({
        state: "UNAVAILABLE",
        canFetch: false,
        targetUrl: normalizedTargetUrl,
        robotsUrl,
        userAgent,
        crawlDelaySeconds: null,
        reason: "unreachable",
      }, startedAt);
    }

    const body = await response.body.text();
    const parsedRobots = parseRobots(robotsUrl, body);
    const allowed = parsedRobots.isAllowed(normalizedTargetUrl, userAgent);

    if (allowed === false) {
      return logResult({
        state: "DISALLOWED",
        canFetch: false,
        targetUrl: normalizedTargetUrl,
        robotsUrl,
        userAgent,
        crawlDelaySeconds: toNumberOrNull(parsedRobots.getCrawlDelay(userAgent)),
        reason: "disallowed",
      }, startedAt);
    }

    return logResult({
      state: "ALLOWED",
      canFetch: true,
      targetUrl: normalizedTargetUrl,
      robotsUrl,
      userAgent,
      crawlDelaySeconds: toNumberOrNull(parsedRobots.getCrawlDelay(userAgent)),
      reason: allowed === true ? "allowed" : "invalid-robots",
    }, startedAt);
  } catch {
    return logResult({
      state: "UNAVAILABLE",
      canFetch: false,
      targetUrl: normalizedTargetUrl,
      robotsUrl,
      userAgent,
      crawlDelaySeconds: null,
      reason: "unreachable",
    }, startedAt);
  }
}

function logResult(
  result: RobotsPolicyResult,
  startedAt: number,
): RobotsPolicyResult {
  logger.info({
    operation: "fetch.robots",
    durationMs: Date.now() - startedAt,
    retryCount: 0,
    errorClass: result.state === "UNAVAILABLE" ? "RobotsUnavailable" : null,
    state: result.state,
    reason: result.reason,
  });

  return result;
}

function toNumberOrNull(value: number | undefined): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}
