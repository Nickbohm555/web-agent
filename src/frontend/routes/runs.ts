import { randomUUID } from "node:crypto";
import { Router } from "express";
import { ZodError } from "zod";
import {
  parseRunStreamEvent,
  createErrorEnvelope,
  createRequestTimer,
  createRunStartResponse,
  parseRunStartRequest,
} from "../contracts.js";

export interface RunEventStreamContext {
  runId: string;
  signal: AbortSignal;
}

export type RunEventStreamFactory = (
  context: RunEventStreamContext,
) => AsyncIterable<unknown>;

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

  router.get("/:runId/events", async (req, res) => {
    const streamFactory = req.app.locals
      .runEventStream as RunEventStreamFactory | undefined;

    res.setHeader("content-type", "text/event-stream; charset=utf-8");
    res.setHeader("cache-control", "no-cache, no-transform");
    res.setHeader("connection", "keep-alive");
    res.flushHeaders();

    const abortController = new AbortController();
    req.on("close", () => {
      abortController.abort();
    });

    if (streamFactory === undefined) {
      res.write(
        serializeRunStreamEvent({
          event: "run_error",
          data: {
            runId: req.params.runId,
            message: "Run event stream is unavailable.",
            code: "STREAM_UNAVAILABLE",
            failedAt: Date.now(),
          },
        }),
      );
      res.end();
      return;
    }

    try {
      for await (const event of streamFactory({
        runId: req.params.runId,
        signal: abortController.signal,
      })) {
        if (abortController.signal.aborted) {
          break;
        }

        const parsedEvent = parseRunStreamEvent(event);
        res.write(serializeRunStreamEvent(parsedEvent));

        if (
          parsedEvent.event === "run_complete" ||
          parsedEvent.event === "run_error"
        ) {
          break;
        }
      }
    } catch {
      if (!abortController.signal.aborted) {
        res.write(
          serializeRunStreamEvent({
            event: "run_error",
            data: {
              runId: req.params.runId,
              message: "Run event stream failed.",
              code: "STREAM_FAILURE",
              failedAt: Date.now(),
            },
          }),
        );
      }
    } finally {
      res.end();
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

function serializeRunStreamEvent(event: unknown): string {
  const parsed = parseRunStreamEvent(event);
  return `event: ${parsed.event}\ndata: ${JSON.stringify(parsed.data)}\n\n`;
}
