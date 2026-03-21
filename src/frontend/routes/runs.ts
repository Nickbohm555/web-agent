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

interface PendingRun {
  prompt: string;
  mode: RunMode;
}

interface BackgroundRunRecord {
  readonly runId: string;
  readonly mode: RunMode;
  readonly events: RunStreamEvent[];
  readonly subscribers: Set<(event: RunStreamEvent) => void>;
  readonly completed: Promise<void>;
  isComplete: boolean;
  completionError: Error | null;
  notifyCompleted: () => void;
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
  const pendingRuns = new Map<string, PendingRun>();
  const backgroundRuns = new Map<string, BackgroundRunRecord>();

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

      startBackgroundRunIfNeeded({
        request,
        runId,
        runEventStreamLike: req.app.locals.runEventStream,
        runExecutorLike: req.app.locals.runExecutor,
        pendingRuns,
        backgroundRuns,
        historyStore: getRunHistoryStore(req.app.locals.runHistoryStore),
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

    const backgroundRun = backgroundRuns.get(req.params.runId);
    if (backgroundRun !== undefined) {
      await streamBackgroundRun({
        run: backgroundRun,
        response: res,
        signal: abortController.signal,
      });
      return;
    }

    if (streamFactory === undefined) {
      res.write(
        serializeRunStreamEvent(
          createRunErrorEvent(
            req.params.runId,
            "Run event stream is unavailable.",
            "STREAM_UNAVAILABLE",
          ),
        ),
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
          serializeRunStreamEvent(
            createRunErrorEvent(
              req.params.runId,
              "Run event stream failed.",
              "STREAM_FAILURE",
            ),
          ),
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
  pendingRuns: Map<string, PendingRun>,
): RunEventStreamFactory {
  return async function* executorBackedStream(
    context: RunEventStreamContext,
  ): AsyncIterable<RunStreamEvent> {
    const pendingRun = pendingRuns.get(context.runId);

    if (pendingRun === undefined) {
      yield createRunErrorEvent(
        context.runId,
        "Run was not found or has already been consumed.",
        "RUN_NOT_FOUND",
      );
      return;
    }

    yield {
      event: "run_state",
      data: createRunningState(context.runId),
    };

    try {
      const result = await executor({
        runId: context.runId,
        signal: context.signal,
        prompt: pendingRun.prompt,
        mode: pendingRun.mode,
      });

      if (result.status === "completed") {
        yield {
          event: "run_complete",
          data: createRunCompleteData(context.runId, result),
        };
        return;
      }

      yield createRunErrorEvent(
        context.runId,
        result.message,
        result.code ?? "RUN_FAILED",
        result.failedAt ?? Date.now(),
      );
    } catch (error: unknown) {
      yield createRunErrorEvent(
        context.runId,
        error instanceof Error ? error.message : "Run execution failed.",
        "RUN_EXECUTION_FAILED",
      );
    } finally {
      pendingRuns.delete(context.runId);
    }
  };
}

function startBackgroundRunIfNeeded(options: {
  request: PendingRun;
  runId: string;
  runEventStreamLike: unknown;
  runExecutorLike: unknown;
  pendingRuns: Map<string, PendingRun>;
  backgroundRuns: Map<string, BackgroundRunRecord>;
  historyStore: RunHistoryStoreLike | null;
}) {
  if (options.request.mode !== "deep_research") {
    return;
  }

  const eventProducer = resolveBackgroundEventProducer(
    options.runEventStreamLike,
    options.runExecutorLike,
    options.request,
    options.runId,
  );

  if (eventProducer === undefined) {
    return;
  }

  const existingRun = options.backgroundRuns.get(options.runId);
  if (existingRun !== undefined) {
    return;
  }

  const run = createBackgroundRunRecord(options.runId, options.request.mode);
  options.backgroundRuns.set(options.runId, run);
  trimBackgroundRuns(options.backgroundRuns);

  void executeBackgroundRun({
    run,
    eventProducer,
    pendingRuns: options.pendingRuns,
    historyStore: options.historyStore,
    backgroundRuns: options.backgroundRuns,
  });
}

function createBackgroundRunRecord(
  runId: string,
  mode: RunMode,
): BackgroundRunRecord {
  let notifyCompleted = () => {};
  const completed = new Promise<void>((resolve) => {
    notifyCompleted = resolve;
  });

  return {
    runId,
    mode,
    events: [],
    subscribers: new Set(),
    completed,
    isComplete: false,
    completionError: null,
    notifyCompleted,
  };
}

async function executeBackgroundRun(options: {
  run: BackgroundRunRecord;
  eventProducer: AsyncIterable<RunStreamEvent>;
  pendingRuns: Map<string, PendingRun>;
  historyStore: RunHistoryStoreLike | null;
  backgroundRuns: Map<string, BackgroundRunRecord>;
}) {
  let nextEventSeq = resolveNextEventSeq(options.historyStore, options.run.runId);

  emitBackgroundRunEvent(options.run, {
    event: "run_state",
    data: createRunningState(options.run.runId),
  });

  try {
    for await (const rawEvent of options.eventProducer) {
      const event = parseRunStreamEvent(rawEvent);
      nextEventSeq = ingestRunStreamEventHistory(
        options.historyStore,
        event,
        nextEventSeq,
      );
      emitBackgroundRunEvent(options.run, event);

      if (event.event === "run_complete" || event.event === "run_error") {
        break;
      }
    }
  } catch (error: unknown) {
    const event = createRunErrorEvent(
      options.run.runId,
      error instanceof Error ? error.message : "Run event stream failed.",
      "STREAM_FAILURE",
    );
    nextEventSeq = ingestRunStreamEventHistory(
      options.historyStore,
      event,
      nextEventSeq,
    );
    emitBackgroundRunEvent(options.run, event);
    options.run.completionError =
      error instanceof Error ? error : new Error(String(error));
  } finally {
    options.pendingRuns.delete(options.run.runId);
    options.run.isComplete = true;
    options.run.notifyCompleted();
    trimBackgroundRuns(options.backgroundRuns);
  }
}

function emitBackgroundRunEvent(run: BackgroundRunRecord, event: RunStreamEvent) {
  run.events.push(event);

  for (const subscriber of run.subscribers) {
    subscriber(event);
  }
}

async function streamBackgroundRun(options: {
  run: BackgroundRunRecord;
  response: import("express").Response;
  signal: AbortSignal;
}) {
  for (const event of options.run.events) {
    if (options.signal.aborted) {
      return;
    }

    options.response.write(serializeRunStreamEvent(event));
  }

  if (options.run.isComplete) {
    options.response.end();
    return;
  }

  await new Promise<void>((resolve) => {
    const subscriber = (event: RunStreamEvent) => {
      if (options.signal.aborted) {
        cleanup();
        resolve();
        return;
      }

      options.response.write(serializeRunStreamEvent(event));
      if (event.event === "run_complete" || event.event === "run_error") {
        cleanup();
        resolve();
      }
    };

    const onAbort = () => {
      cleanup();
      resolve();
    };

    const cleanup = () => {
      options.run.subscribers.delete(subscriber);
      options.signal.removeEventListener("abort", onAbort);
    };

    options.run.subscribers.add(subscriber);
    options.signal.addEventListener("abort", onAbort, { once: true });
    void options.run.completed.then(() => {
      cleanup();
      resolve();
    });
  });

  options.response.end();
}

function resolveBackgroundEventProducer(
  streamFactoryLike: unknown,
  executorLike: unknown,
  request: PendingRun,
  runId: string,
): AsyncIterable<RunStreamEvent> | undefined {
  if (typeof streamFactoryLike === "function") {
    return createValidatedEventProducer(
      (streamFactoryLike as RunEventStreamFactory)({
        runId,
        signal: new AbortController().signal,
      }),
    );
  }

  if (typeof executorLike === "function") {
    return createExecutorBackedEventProducer(executorLike as RunExecutor, {
      runId,
      prompt: request.prompt,
      mode: request.mode,
    });
  }

  return undefined;
}

async function* createValidatedEventProducer(
  source: AsyncIterable<unknown>,
): AsyncIterable<RunStreamEvent> {
  for await (const event of source) {
    yield parseRunStreamEvent(event);
  }
}

async function* createExecutorBackedEventProducer(
  executor: RunExecutor,
  run: PendingRun & { runId: string },
): AsyncIterable<RunStreamEvent> {
  const result = await executor({
    runId: run.runId,
    signal: new AbortController().signal,
    prompt: run.prompt,
    mode: run.mode,
  });

  if (result.status === "completed") {
    yield {
      event: "run_complete",
      data: createRunCompleteData(run.runId, result),
    };
    return;
  }

  yield createRunErrorEvent(
    run.runId,
    result.message,
    result.code ?? "RUN_FAILED",
    result.failedAt ?? Date.now(),
  );
}

function trimBackgroundRuns(backgroundRuns: Map<string, BackgroundRunRecord>) {
  const MAX_BACKGROUND_RUNS = 25;

  while (backgroundRuns.size > MAX_BACKGROUND_RUNS) {
    const oldestCompletedRun = [...backgroundRuns.values()].find((run) => run.isComplete);
    if (oldestCompletedRun === undefined) {
      return;
    }

    backgroundRuns.delete(oldestCompletedRun.runId);
  }
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
      const responseRecord = asRecord(payload);
      const finalAnswer = responseRecord.final_answer;
      const elapsedMs = responseRecord.elapsed_ms;

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
  pendingRuns: Map<string, PendingRun>,
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
    case "run_complete": {
      const completedAt = toIsoTimestamp(event.data.completedAt);
      ingestRunHistoryEvent(
        store,
        createRunCompletionEvent(
          event.data.runId,
          nextEventSeq,
          "final_answer_generated",
          completedAt,
          event.data.finalAnswer,
        ),
      );
      ingestRunHistoryEvent(
        store,
        createRunCompletionEvent(
          event.data.runId,
          nextEventSeq + 1,
          "run_completed",
          completedAt,
          event.data.finalAnswer,
        ),
      );
      return nextEventSeq + 2;
    }
    case "run_error":
      ingestRunHistoryEvent(
        store,
        createRunFailureEvent(
          event.data.runId,
          nextEventSeq,
          event.data.failedAt,
          event.data.message,
          event.data.code,
        ),
      );
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
      ...createToolEventBase(event, eventSeq, completedAt),
      event_type: "tool_call_succeeded",
      tool_output: toPreviewPayload(event.outputPreview),
    };
  }

  if (event.status === "failed") {
    return {
      ...createToolEventBase(event, eventSeq, completedAt),
      event_type: "tool_call_failed",
      tool_input: toPreviewPayload(event.inputPreview),
      error_output: {
        message: event.error ?? "Tool call failed.",
      },
    };
  }

  return {
    ...createToolEventBase(event, eventSeq, event.startedAt ?? Date.now()),
    event_type: "tool_call_started",
    tool_input: toPreviewPayload(event.inputPreview),
  };
}

function createToolEventBase(
  event: ToolCallEvent,
  eventSeq: number,
  timestamp: number,
) {
  return {
    run_id: event.runId,
    event_seq: eventSeq,
    ts: toIsoTimestamp(timestamp),
    tool_name: event.toolName,
    tool_call_id: event.toolCallId,
    safety: createEmptyRunEventSafety(),
  };
}

function createRunCompletionEvent(
  runId: string,
  eventSeq: number,
  eventType: "final_answer_generated" | "run_completed",
  timestamp: string,
  finalAnswer: string,
): CanonicalRunEvent {
  return {
    run_id: runId,
    event_seq: eventSeq,
    event_type: eventType,
    ts: timestamp,
    final_answer: finalAnswer,
    safety: createEmptyRunEventSafety(),
  };
}

function createRunFailureEvent(
  runId: string,
  eventSeq: number,
  failedAt: number,
  message: string,
  code?: string,
): CanonicalRunEvent {
  return {
    run_id: runId,
    event_seq: eventSeq,
    event_type: "run_failed",
    ts: toIsoTimestamp(failedAt),
    error_output: {
      code: code ?? "RUN_FAILED",
      message,
    },
    safety: createEmptyRunEventSafety(),
  };
}

function createRunErrorEvent(
  runId: string,
  message: string,
  code: string,
  failedAt = Date.now(),
): RunStreamEvent {
  return {
    event: "run_error",
    data: {
      runId,
      message,
      code,
      failedAt,
    },
  };
}

function createRunCompleteData(
  runId: string,
  result: Extract<RunExecutorResult, { status: "completed" }>,
) {
  return {
    runId,
    finalAnswer: result.finalAnswer,
    completedAt: result.completedAt ?? Date.now(),
    durationMs: result.durationMs ?? 0,
  };
}

function createRunningState(runId: string) {
  return {
    runId,
    state: "running" as const,
    ts: Date.now(),
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

function toIsoTimestamp(timestamp: number): string {
  return new Date(timestamp).toISOString();
}

function toPreviewPayload(preview: string | undefined): { preview: string } | undefined {
  return preview === undefined ? undefined : { preview };
}

function serializeRunStreamEvent(event: unknown): string {
  const parsed = parseRunStreamEvent(event);
  return `event: ${parsed.event}\ndata: ${JSON.stringify(parsed.data)}\n\n`;
}
