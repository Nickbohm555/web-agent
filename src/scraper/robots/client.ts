import pino from "pino";
import { request, type Dispatcher } from "undici";

export type RobotsFetchState = "OK" | "MISSING" | "UNAVAILABLE";

type RequestLike = typeof request;

export interface FetchRobotsTxtOptions {
  requestFn?: RequestLike;
  dispatcher?: Dispatcher;
  timeoutMs?: number;
  userAgent?: string;
}

export type FetchRobotsTxtResult =
  | {
      state: "OK";
      robotsUrl: string;
      statusCode: number;
      body: string;
      fetchedAt: string;
    }
  | {
      state: "MISSING";
      robotsUrl: string;
      statusCode: 404;
      fetchedAt: string;
    }
  | {
      state: "UNAVAILABLE";
      robotsUrl: string;
      statusCode: number | null;
      fetchedAt: string;
      errorClass: string | null;
    };

const DEFAULT_TIMEOUT_MS = 5_000;
const logger = pino({ level: process.env.LOG_LEVEL ?? "silent" });

export async function fetchRobotsTxt(
  targetUrl: string,
  options: FetchRobotsTxtOptions = {},
): Promise<FetchRobotsTxtResult> {
  const normalizedTargetUrl = new URL(targetUrl).toString();
  const robotsUrl = new URL("/robots.txt", normalizedTargetUrl).toString();
  const startedAt = Date.now();
  const requestFn = options.requestFn ?? request;

  try {
    const response = await requestFn(robotsUrl, {
      method: "GET",
      headers: {
        "user-agent": options.userAgent ?? "web-agent-bot",
      },
      headersTimeout: options.timeoutMs ?? DEFAULT_TIMEOUT_MS,
      bodyTimeout: options.timeoutMs ?? DEFAULT_TIMEOUT_MS,
      ...(options.dispatcher ? { dispatcher: options.dispatcher } : {}),
    });

    if (response.statusCode === 404) {
      return logResult(
        {
          state: "MISSING",
          robotsUrl,
          statusCode: 404,
          fetchedAt: new Date().toISOString(),
        },
        startedAt,
      );
    }

    if (response.statusCode >= 400) {
      return logResult(
        {
          state: "UNAVAILABLE",
          robotsUrl,
          statusCode: response.statusCode,
          fetchedAt: new Date().toISOString(),
          errorClass: "RobotsHttpError",
        },
        startedAt,
      );
    }

    return logResult(
      {
        state: "OK",
        robotsUrl,
        statusCode: response.statusCode,
        body: await response.body.text(),
        fetchedAt: new Date().toISOString(),
      },
      startedAt,
    );
  } catch (error) {
    return logResult(
      {
        state: "UNAVAILABLE",
        robotsUrl,
        statusCode: null,
        fetchedAt: new Date().toISOString(),
        errorClass: error instanceof Error ? error.name : "UnknownError",
      },
      startedAt,
    );
  }
}

function logResult(
  result: FetchRobotsTxtResult,
  startedAt: number,
): FetchRobotsTxtResult {
  logger.info({
    operation: "fetch.robots.request",
    durationMs: Date.now() - startedAt,
    retryCount: 0,
    errorClass: result.state === "UNAVAILABLE" ? result.errorClass : null,
    state: result.state,
    statusCode: "statusCode" in result ? result.statusCode : null,
  });

  return result;
}
