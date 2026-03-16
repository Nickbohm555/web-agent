import pino from "pino";
import { request, type Dispatcher } from "undici";
import { z } from "zod";

import { executeWithRetry } from "../../core/retry.js";
import {
  normalizeSearchRequest,
  type SearchOptions,
} from "../../sdk/contracts/search.js";
import type { ResolvedSearchControls } from "../../core/policy/retrieval-controls.js";
import { buildSerperSearchRequest } from "./search-request.js";

const SERPER_API_URL = "https://google.serper.dev/search";
const SERPER_TIMEOUT_MS = 5_000;
const logger = pino({ level: process.env.LOG_LEVEL ?? "silent" });

const SerperOrganicResultSchema = z
  .object({
    title: z.string().optional(),
    link: z.string().optional(),
    snippet: z.string().optional(),
    position: z.number().int().positive().optional(),
  })
  .passthrough();

const SerperSearchResponseSchema = z
  .object({
    organic: z.array(SerperOrganicResultSchema).default([]),
  })
  .passthrough();

type SerperSearchResponse = z.output<typeof SerperSearchResponseSchema>;

type RequestLike = typeof request;

export interface SerperClientOptions {
  apiKey?: string;
  endpoint?: string;
  requestFn?: RequestLike;
  dispatcher?: Dispatcher;
  timeoutMs?: number;
}

export interface SerperClientResult {
  payload: SerperSearchResponse;
  meta: {
    attempts: number;
    retries: number;
    durationMs: number;
  };
}

export async function callSerperSearch(
  query: string,
  options?: SearchOptions | ResolvedSearchControls,
  clientOptions: SerperClientOptions = {},
): Promise<SerperClientResult> {
  const normalizedRequest = isResolvedSearchControls(options)
    ? {
        query: normalizeSearchRequest(query).query,
        options,
      }
    : normalizeSearchRequest(query, options);
  const apiKey = clientOptions.apiKey ?? process.env.SERPER_API_KEY;

  if (!apiKey) {
    throw new Error("Missing SERPER_API_KEY");
  }

  const requestFn = clientOptions.requestFn ?? request;
  const startedAt = Date.now();

  try {
    const result = await executeWithRetry(
      async () => {
        const signal = AbortSignal.timeout(
          clientOptions.timeoutMs ?? normalizedRequest.options.timeoutMs,
        );
        const response = await requestFn(clientOptions.endpoint ?? SERPER_API_URL, {
          method: "POST",
          headers: {
            "content-type": "application/json",
            "x-api-key": apiKey,
          },
          body: JSON.stringify(
            buildSerperSearchRequest(normalizedRequest.query, normalizedRequest.options),
          ),
          signal,
          headersTimeout: clientOptions.timeoutMs ?? SERPER_TIMEOUT_MS,
          bodyTimeout: clientOptions.timeoutMs ?? SERPER_TIMEOUT_MS,
          ...(clientOptions.dispatcher ? { dispatcher: clientOptions.dispatcher } : {}),
        });

        const payload = await response.body.json();

        if (response.statusCode === 429 || response.statusCode >= 500) {
          throw new SerperHttpError(
            `Retryable Serper status ${response.statusCode}`,
            response.statusCode,
          );
        }

        if (response.statusCode >= 400) {
          throw new NonRetryableSerperError(
            `Non-retryable Serper status ${response.statusCode}`,
            response.statusCode,
          );
        }

        return SerperSearchResponseSchema.parse(payload);
      },
      (error) => {
        if (error instanceof NonRetryableSerperError) {
          return {
            retryable: false,
            reason: "non-retryable-status",
          };
        }

        if (error instanceof SerperHttpError) {
          return {
            retryable: true,
            reason: "retryable-status",
          };
        }

        if (error instanceof z.ZodError) {
          return {
            retryable: false,
            reason: "invalid-provider-payload",
          };
        }

        return {
          retryable: isRetryableTransportError(error),
          reason: "transport-error",
        };
      },
    );

    const durationMs = Date.now() - startedAt;
    logger.info({
      operation: "serper.search",
      durationMs,
      retryCount: result.retries,
      errorClass: null,
    });

    return {
      payload: result.value,
      meta: {
        attempts: result.attempts,
        retries: result.retries,
        durationMs,
      },
    };
  } catch (error) {
    const durationMs = Date.now() - startedAt;
    logger.error({
      operation: "serper.search",
      durationMs,
      retryCount: error instanceof Error && "attemptNumber" in error ? Number(error.attemptNumber) - 1 : 0,
      errorClass: error instanceof Error ? error.constructor.name : "UnknownError",
    });

    throw unwrapAbortCause(error);
  }
}

export type { SerperSearchResponse };

function isResolvedSearchControls(
  value: SearchOptions | ResolvedSearchControls | undefined,
): value is ResolvedSearchControls {
  return typeof value === "object" && value !== null && "domainScope" in value;
}

function isRetryableTransportError(error: unknown): boolean {
  if (!(error instanceof Error)) {
    return false;
  }

  const transportErrorCodes = new Set([
    "ECONNRESET",
    "ECONNREFUSED",
    "EPIPE",
    "ETIMEDOUT",
    "ABORT_ERR",
    "UND_ERR_CONNECT_TIMEOUT",
    "UND_ERR_HEADERS_TIMEOUT",
    "UND_ERR_BODY_TIMEOUT",
  ]);

  const code = "code" in error ? error.code : undefined;
  return typeof code === "string" && transportErrorCodes.has(code);
}

function unwrapAbortCause(error: unknown): unknown {
  if (error instanceof Error && "originalError" in error) {
    return error.originalError;
  }

  if (error instanceof Error && "cause" in error && error.cause) {
    return error.cause;
  }

  return error;
}

class SerperHttpError extends Error {
  constructor(
    message: string,
    readonly statusCode: number,
  ) {
    super(message);
    this.name = "SerperHttpError";
  }
}

class NonRetryableSerperError extends Error {
  constructor(
    message: string,
    readonly statusCode: number,
  ) {
    super(message);
    this.name = "NonRetryableSerperError";
  }
}
