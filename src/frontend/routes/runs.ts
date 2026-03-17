import { randomUUID } from "node:crypto";
import { Router } from "express";
import { ZodError } from "zod";
import {
  createErrorEnvelope,
  createRequestTimer,
  createRunStartResponse,
  parseRunStartRequest,
} from "../contracts.js";

export function createRunsRouter(): Router {
  const router = Router();

  router.post("/", (req, res) => {
    const startedAt = createRequestTimer();

    try {
      parseRunStartRequest(req.body);

      res.status(201).json(
        createRunStartResponse({
          runId: randomUUID(),
          status: "queued",
        }),
      );
    } catch (error: unknown) {
      const request =
        error instanceof ZodError ? null : safelyParseRequest(req.body);
      const envelope = createErrorEnvelope({
        operation: "run_start",
        request,
        startedAt,
        error,
      });

      res.status(resolveStatusCode(error)).json(envelope);
    }
  });

  return router;
}

function safelyParseRequest(input: unknown) {
  try {
    return parseRunStartRequest(input);
  } catch {
    return null;
  }
}

function resolveStatusCode(error: unknown): number {
  if (error instanceof ZodError) {
    return 400;
  }

  return 500;
}
