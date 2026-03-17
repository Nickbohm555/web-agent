import { Router } from "express";
import { createToolCallId, emitToolCallFailed, emitToolCallStarted, emitToolCallSucceeded } from "../../core/telemetry/observability-logger.js";
import { ZodError } from "zod";
import { search } from "../../sdk/search.js";
import {
  createErrorEnvelope,
  createRequestTimer,
  createSearchSuccessEnvelope,
  parseSearchApiRequest,
  parseSearchSdkOptions,
} from "../contracts.js";

export function createSearchRouter(): Router {
  const router = Router();

  router.post("/", async (req, res) => {
    const startedAt = createRequestTimer();
    const toolCallId = createToolCallId();
    let requestBody: unknown = req.body;

    try {
      const request = parseSearchApiRequest(req.body);
      requestBody = request;
      emitToolCallStarted({
        toolName: "web_search",
        toolCallId,
        toolInput: request,
      });
      const data = await search(request.query, parseSearchSdkOptions(req.body));
      emitToolCallSucceeded({
        toolName: "web_search",
        toolCallId,
        toolOutput: data,
      });

      res.json(
        createSearchSuccessEnvelope({
          request,
          data,
          startedAt,
        }),
      );
    } catch (error: unknown) {
      const request =
        error instanceof ZodError ? null : safelyParseRequest(req.body);
      const envelope = createErrorEnvelope({
        operation: "search",
        request,
        startedAt,
        error,
      });
      emitToolCallFailed({
        toolName: "web_search",
        toolCallId,
        ...(requestBody !== undefined ? { toolInput: requestBody } : {}),
        errorOutput: {
          statusCode: resolveStatusCode(error),
          error: envelope.ok ? null : envelope.error,
        },
      });

      res.status(resolveStatusCode(error)).json(envelope);
    }
  });

  return router;
}

function safelyParseRequest(input: unknown) {
  try {
    return parseSearchApiRequest(input);
  } catch {
    return null;
  }
}

function resolveStatusCode(error: unknown): number {
  if (error instanceof ZodError) {
    return 400;
  }

  if (error instanceof Error && "kind" in error) {
    switch (error.kind) {
      case "rate_limited":
        return 429;
      case "timeout":
        return 504;
      case "network":
      case "provider_unavailable":
        return 503;
      case "invalid_request":
        return 400;
      case "policy_denied":
        return 403;
      case "content_unavailable":
        return 404;
      case "unknown":
        return 500;
    }
  }

  return 500;
}
