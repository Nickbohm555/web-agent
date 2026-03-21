import { randomUUID } from "node:crypto";
import { Router } from "express";
import { ZodError } from "zod";
import {
  createEmptyRunEventSafety,
  parseRunStreamEvent,
  createErrorEnvelope,
  createRequestTimer,
  createRunStartResponse,
  parseRunStartRequest,
  type CanonicalRunEvent,
  type RunMode,
  type RunHistoryRunSnapshot,
  type RunStreamEvent,
  type ToolCallEvent,
} from "../contracts.js";

export interface RunEventStreamContext {
  runId: string;
  signal: AbortSignal;
}

export interface RunExecutorContext extends RunEventStreamContext {
  prompt: string;
  mode: RunMode;
}

export type RunExecutorResult =
  | {
    status: "completed";
    finalAnswer: string;
    durationMs?: number;
    completedAt?: number;
  }
  | {
    status: "failed";
    message: string;
    code?: string;
    failedAt?: number;
  };

export type RunEventStreamFactory = (
  context: RunEventStreamContext,
) => AsyncIterable<unknown>;

export type RunExecutor = (
  context: RunExecutorContext,
) => Promise<RunExecutorResult> | RunExecutorResult;

interface RunHistoryStoreLike {
  ingest(event: unknown): void;
  getRun(runId: string): RunHistoryRunSnapshot | null;
}

export function createRunsRouter(): Router {
  const router = Router();
  const pendingRuns = new Map<string, { prompt: string; mode: RunMode }>();

  router.post("/", (req, res) => {
    const startedAt = createRequestTimer();

    try {
      const request = parseRunStartRequest(req.body);
      const runId = randomUUID();
      pendingRuns.set(runId, request);

      ingestRunHistoryEvent(req.app.locals.runHistoryStore, {
        run_id: runId,
        event_seq: 0,
        event_type: "run_started",
        ts: new Date().toISOString(),
        tool_input: {
          prompt: request.prompt,
          mode: request.mode,
        },
        safety: createEmptyRunEventSafety(),
      });

      res.status(201).json(
        createRunStartResponse({
          runId,
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
    const streamFactory = resolveRunEventStreamFactory(
      req.app.locals.runEventStream,
      req.app.locals.runExecutor,
      pendingRuns,
    );
    const historyStore = getRunHistoryStore(req.app.locals.runHistoryStore);
    let nextEventSeq = resolveNextEventSeq(historyStore, req.params.runId);

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
        nextEventSeq = ingestRunStreamEventHistory(
          historyStore,
          parsedEvent,
          nextEventSeq,
        );
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

export function createExecutorBackedRunEventStreamFactory(
  executor: RunExecutor,
  pendingRuns: Map<string, { prompt: string; mode: RunMode }>,
): RunEventStreamFactory {
  return async function* executorBackedStream(
    context: RunEventStreamContext,
  ): AsyncIterable<RunStreamEvent> {
    const pendingRun = pendingRuns.get(context.runId);

    if (pendingRun === undefined) {
      yield {
        event: "run_error",
        data: {
          runId: context.runId,
          message: "Run was not found or has already been consumed.",
          code: "RUN_NOT_FOUND",
          failedAt: Date.now(),
        },
      };
      return;
    }

    yield {
      event: "run_state",
      data: {
        runId: context.runId,
        state: "running",
        ts: Date.now(),
      },
    };

    try {
      const result = await executor({
        runId: context.runId,
        signal: context.signal,
        prompt: pendingRun.prompt,
        mode: pendingRun.mode,
      });

      if (result.status === "completed") {
        const completedAt = result.completedAt ?? Date.now();
        yield {
          event: "run_complete",
          data: {
            runId: context.runId,
            finalAnswer: result.finalAnswer,
            completedAt,
            durationMs: result.durationMs ?? 0,
          },
        };
        return;
      }

      yield {
        event: "run_error",
        data: {
          runId: context.runId,
          message: result.message,
          code: result.code ?? "RUN_FAILED",
          failedAt: result.failedAt ?? Date.now(),
        },
      };
    } catch (error: unknown) {
      yield {
        event: "run_error",
        data: {
          runId: context.runId,
          message:
            error instanceof Error ? error.message : "Run execution failed.",
          code: "RUN_EXECUTION_FAILED",
          failedAt: Date.now(),
        },
      };
    } finally {
      pendingRuns.delete(context.runId);
    }
  };
}

export function createHttpAgentRunExecutor(
  backendOrigin: string,
  fetchImplementation: typeof fetch = fetch,
): RunExecutor {
  return async function httpAgentRunExecutor(
    context: RunExecutorContext,
  ): Promise<RunExecutorResult> {
    const response = await fetchImplementation(
      new URL("/api/agent/run", backendOrigin),
      {
        method: "POST",
        headers: {
          "content-type": "application/json",
        },
        body: JSON.stringify({
          prompt: context.prompt,
          mode: context.mode,
        }),
        signal: context.signal,
      },
    );

    const payload = await safelyReadJson(response);
    if (response.ok) {
      const finalAnswer =
        asRecord(payload).final_answer;
      const elapsedMs = asRecord(payload).elapsed_ms;

      if (typeof finalAnswer !== "string" || typeof elapsedMs !== "number") {
        throw new Error("Backend agent response failed validation.");
      }

      return {
        status: "completed",
        finalAnswer,
        durationMs: elapsedMs,
        completedAt: Date.now(),
      };
    }

    const errorPayload = asRecord(asRecord(payload).error);
    return {
      status: "failed",
      message:
        typeof errorPayload.message === "string"
          ? errorPayload.message
          : `Backend agent route failed with status ${response.status}.`,
      code:
        typeof errorPayload.code === "string"
          ? errorPayload.code
          : "RUN_FAILED",
      failedAt: Date.now(),
    };
  };
}

function getRunHistoryStore(input: unknown): RunHistoryStoreLike | null {
  if (
    typeof input !== "object" ||
    input === null ||
    typeof (input as RunHistoryStoreLike).ingest !== "function" ||
    typeof (input as RunHistoryStoreLike).getRun !== "function"
  ) {
    return null;
  }

  return input as RunHistoryStoreLike;
}

function resolveRunEventStreamFactory(
  streamFactoryLike: unknown,
  executorLike: unknown,
  pendingRuns: Map<string, { prompt: string; mode: RunMode }>,
): RunEventStreamFactory | undefined {
  if (typeof streamFactoryLike === "function") {
    return streamFactoryLike as RunEventStreamFactory;
  }

  if (typeof executorLike === "function") {
    return createExecutorBackedRunEventStreamFactory(
      executorLike as RunExecutor,
      pendingRuns,
    );
  }

  return undefined;
}

function resolveNextEventSeq(
  store: RunHistoryStoreLike | null,
  runId: string,
): number {
  return (store?.getRun(runId)?.events.at(-1)?.event_seq ?? -1) + 1;
}

function ingestRunStreamEventHistory(
  store: RunHistoryStoreLike | null,
  event: RunStreamEvent,
  nextEventSeq: number,
): number {
  if (store === null) {
    return nextEventSeq;
  }

  switch (event.event) {
    case "run_state":
      return nextEventSeq;
    case "tool_call":
      ingestRunHistoryEvent(store, createCanonicalToolEvent(event.data, nextEventSeq));
      return nextEventSeq + 1;
    case "run_complete":
      ingestRunHistoryEvent(store, {
        run_id: event.data.runId,
        event_seq: nextEventSeq,
        event_type: "final_answer_generated",
        ts: new Date(event.data.completedAt).toISOString(),
        final_answer: event.data.finalAnswer,
        safety: createEmptyRunEventSafety(),
      });
      ingestRunHistoryEvent(store, {
        run_id: event.data.runId,
        event_seq: nextEventSeq + 1,
        event_type: "run_completed",
        ts: new Date(event.data.completedAt).toISOString(),
        final_answer: event.data.finalAnswer,
        safety: createEmptyRunEventSafety(),
      });
      return nextEventSeq + 2;
    case "run_error":
      ingestRunHistoryEvent(store, {
        run_id: event.data.runId,
        event_seq: nextEventSeq,
        event_type: "run_failed",
        ts: new Date(event.data.failedAt).toISOString(),
        error_output: {
          code: event.data.code ?? "RUN_FAILED",
          message: event.data.message,
        },
        safety: createEmptyRunEventSafety(),
      });
      return nextEventSeq + 1;
  }
}

function createCanonicalToolEvent(
  event: ToolCallEvent,
  eventSeq: number,
): CanonicalRunEvent {
  const completedAt = event.endedAt ?? event.startedAt ?? Date.now();

  if (event.status === "completed") {
    return {
      run_id: event.runId,
      event_seq: eventSeq,
      event_type: "tool_call_succeeded",
      ts: new Date(completedAt).toISOString(),
      tool_name: event.toolName,
      tool_call_id: event.toolCallId,
      tool_output: event.outputPreview === undefined
        ? undefined
        : { preview: event.outputPreview },
      safety: createEmptyRunEventSafety(),
    };
  }

  if (event.status === "failed") {
    return {
      run_id: event.runId,
      event_seq: eventSeq,
      event_type: "tool_call_failed",
      ts: new Date(completedAt).toISOString(),
      tool_name: event.toolName,
      tool_call_id: event.toolCallId,
      tool_input: event.inputPreview === undefined
        ? undefined
        : { preview: event.inputPreview },
      error_output: {
        message: event.error ?? "Tool call failed.",
      },
      safety: createEmptyRunEventSafety(),
    };
  }

  return {
    run_id: event.runId,
    event_seq: eventSeq,
    event_type: "tool_call_started",
    ts: new Date(event.startedAt ?? Date.now()).toISOString(),
    tool_name: event.toolName,
    tool_call_id: event.toolCallId,
    tool_input: event.inputPreview === undefined
      ? undefined
      : { preview: event.inputPreview },
    safety: createEmptyRunEventSafety(),
  };
}

function ingestRunHistoryEvent(
  storeLike: unknown,
  event: CanonicalRunEvent,
) {
  getRunHistoryStore(storeLike)?.ingest(event);
}

function safelyParseRequest(input: unknown) {
  try {
    return parseRunStartRequest(input);
  } catch {
    return null;
  }
}

async function safelyReadJson(response: Response): Promise<unknown> {
  try {
    return await response.json();
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

function asRecord(input: unknown): Record<string, unknown> {
  if (typeof input !== "object" || input === null || Array.isArray(input)) {
    return {};
  }

  return input as Record<string, unknown>;
}

function serializeRunStreamEvent(event: unknown): string {
  const parsed = parseRunStreamEvent(event);
  return `event: ${parsed.event}\ndata: ${JSON.stringify(parsed.data)}\n\n`;
}
