import { randomUUID } from "node:crypto";
import { Router } from "express";
import { ZodError } from "zod";
import {
  createEmptyRunEventSafety,
  createErrorEnvelope,
  createRequestTimer,
  createRunStartResponse,
  parseBackendAgentRunSuccessResponse,
  parseRunStartRequest,
  parseRunStreamEvent,
  type CanonicalRunEvent,
  type RetrievalActionEvent,
  type RunHistoryRunSnapshot,
  type RunMode,
  type RunRetrievalPolicy,
  type RunSource,
  type StructuredAnswer,
  type RunStreamEvent,
  type ToolCallEvent,
} from "../contracts.js";
import { withRunContext } from "../../core/telemetry/run-context.js";

export interface RunEventStreamContext {
  runId: string;
  signal: AbortSignal;
}

export interface RunExecutorContext extends RunEventStreamContext {
  prompt: string;
  mode: RunMode;
  retrievalPolicy: RunRetrievalPolicy;
}

interface PendingRun {
  prompt: string;
  mode: RunMode;
  retrievalPolicy: RunRetrievalPolicy;
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

const DEFAULT_RUN_FAILED_CODE = "RUN_FAILED";
const MAX_BACKGROUND_RUNS = 25;
const MAX_ACTIVE_BACKGROUND_RUNS = 3;
const MAX_BACKGROUND_EVENTS_PER_RUN = 100;

export type RunExecutorResult =
  | {
    status: "completed";
    finalAnswer: string;
    structuredAnswer?: StructuredAnswer;
    sources: RunSource[];
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
      if (
        request.mode === "deep_research" &&
        countActiveBackgroundRuns(backgroundRuns) >= MAX_ACTIVE_BACKGROUND_RUNS
      ) {
        res.status(429).json(
          createRunStartRateLimitEnvelope({
            request,
            startedAt,
            message: "Too many deep research runs are already active.",
          }),
        );
        return;
      }
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
          retrievalPolicy: serializeRunRetrievalPolicy(request.retrievalPolicy),
        },
        safety: createEmptyRunEventSafety(),
      });
      ingestRunHistoryEvent(
        req.app.locals.runHistoryStore,
        createRunProgressEvent(
          runId,
          1,
          "research_planning_started",
          new Date().toISOString(),
          {
            stage: "planning",
            message: getPlanningMessage(request.mode),
          },
          {
            prompt: request.prompt,
            mode: request.mode,
          },
        ),
      );

      startBackgroundRunIfNeeded({
        request,
        runId,
        runEventStreamLike: req.app.locals.runEventStream,
        runExecutorLike: req.app.locals.runExecutor,
        pendingRuns,
        backgroundRuns,
        historyStore: getRunHistoryStore(req.app.locals.runHistoryStore),
      });

      const startResponse =
        request.mode === "deep_research"
          ? createRunStartResponse({
              runId,
              status: "queued",
              metadata: {
                execution_surface: "background",
              },
            })
          : createRunStartResponse({
              runId,
              status: "queued",
            });

      res.status(201).json(startResponse);
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
          createRunStreamUnavailableEvent(req.params.runId),
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

        if (isTerminalRunStreamEvent(parsedEvent)) {
          break;
        }
      }
    } catch {
      if (!abortController.signal.aborted) {
        res.write(serializeRunStreamEvent(createRunStreamFailureEvent(req.params.runId)));
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
      yield createRunNotFoundEvent(context.runId);
      return;
    }

    yield createRunningRunStateEvent(context.runId);

    try {
      const result = await executor(
        createRunExecutorContext(context.runId, context.signal, pendingRun),
      );
      yield createRunExecutorEvent(context.runId, result);
    } catch (error: unknown) {
      yield createRunExecutionFailureEvent(context.runId, error);
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

  await withRunContext(
    async () => {
      emitBackgroundRunEvent(options.run, createRunningRunStateEvent(options.run.runId));

      try {
        for await (const rawEvent of options.eventProducer) {
          const event = parseRunStreamEvent(rawEvent);
          nextEventSeq = ingestRunStreamEventHistory(
            options.historyStore,
            event,
            nextEventSeq,
          );
          emitBackgroundRunEvent(options.run, event);

          if (isTerminalRunStreamEvent(event)) {
            break;
          }
        }
      } catch (error: unknown) {
        const event = createRunStreamFailureEvent(options.run.runId, error);
        nextEventSeq = ingestRunStreamEventHistory(
          options.historyStore,
          event,
          nextEventSeq,
        );
        emitBackgroundRunEvent(options.run, event);
        options.run.completionError =
          error instanceof Error ? error : new Error(String(error));
      } finally {
        finalizeBackgroundRun(options);
      }
    },
    {
      runId: options.run.runId,
      initialEventSeq: nextEventSeq,
    },
  );
}

function emitBackgroundRunEvent(run: BackgroundRunRecord, event: RunStreamEvent) {
  run.events.push(event);
  while (run.events.length > MAX_BACKGROUND_EVENTS_PER_RUN) {
    run.events.shift();
  }

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
      if (isTerminalRunStreamEvent(event)) {
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
    return createExecutorBackedEventProducer(
      executorLike as RunExecutor,
      runId,
      request,
    );
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
  runId: string,
  run: PendingRun,
): AsyncIterable<RunStreamEvent> {
  const result = await executor(
    createRunExecutorContext(runId, new AbortController().signal, run),
  );
  yield createRunExecutorEvent(runId, result);
}

function finalizeBackgroundRun(options: {
  run: BackgroundRunRecord;
  pendingRuns: Map<string, PendingRun>;
  backgroundRuns: Map<string, BackgroundRunRecord>;
}) {
  options.pendingRuns.delete(options.run.runId);
  options.run.isComplete = true;
  options.run.notifyCompleted();
  trimBackgroundRuns(options.backgroundRuns);
}

function trimBackgroundRuns(backgroundRuns: Map<string, BackgroundRunRecord>) {
  while (backgroundRuns.size > MAX_BACKGROUND_RUNS) {
    const oldestCompletedRun = [...backgroundRuns.values()].find((run) => run.isComplete);
    if (oldestCompletedRun === undefined) {
      return;
    }

    backgroundRuns.delete(oldestCompletedRun.runId);
  }
}

function countActiveBackgroundRuns(
  backgroundRuns: Map<string, BackgroundRunRecord>,
): number {
  let activeRuns = 0;

  for (const run of backgroundRuns.values()) {
    if (!run.isComplete) {
      activeRuns += 1;
    }
  }

  return activeRuns;
}

function isTerminalRunStreamEvent(event: RunStreamEvent): boolean {
  return event.event === "run_complete" || event.event === "run_error";
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
          retrievalPolicy: serializeBackendRetrievalPolicy(context.retrievalPolicy),
        }),
        signal: context.signal,
      },
    );

    const payload = await safelyReadJson(response);
    if (response.ok) {
      const responseRecord = parseBackendAgentRunSuccessResponse(payload);

      return {
        status: "completed",
        finalAnswer: responseRecord.final_answer.text,
        structuredAnswer: responseRecord.final_answer,
        sources: responseRecord.sources,
        durationMs: responseRecord.elapsed_ms,
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

function serializeRunRetrievalPolicy(policy: RunRetrievalPolicy) {
  const { search, fetch } = policy;
  return {
    search: serializeSearchPolicy(search),
    fetch: serializeFetchPolicy(fetch),
  };
}

function serializeBackendRetrievalPolicy(policy: RunRetrievalPolicy) {
  const { search, fetch } = policy;
  return {
    search: serializeBackendSearchPolicy(search),
    fetch: serializeBackendFetchPolicy(fetch),
  };
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
    case "retrieval_action": {
      const progressEvents = createRetrievalProgressEvents(event.data, nextEventSeq);
      for (const progressEvent of progressEvents) {
        ingestRunHistoryEvent(store, progressEvent);
      }
      ingestRunHistoryEvent(
        store,
        createCanonicalRetrievalActionEvent(
          event.data,
          nextEventSeq + progressEvents.length,
        ),
      );
      return nextEventSeq + progressEvents.length + 1;
    }
    case "tool_call": {
      const progressEvents = createToolProgressEvents(event.data, nextEventSeq);
      for (const progressEvent of progressEvents) {
        ingestRunHistoryEvent(store, progressEvent);
      }
      const sourceExpansionEvents = createSourceExpansionEvents(
        store,
        event.data,
        nextEventSeq + progressEvents.length,
      );
      for (const sourceExpansionEvent of sourceExpansionEvents) {
        ingestRunHistoryEvent(store, sourceExpansionEvent);
      }
      ingestRunHistoryEvent(
        store,
        createCanonicalToolEvent(
          event.data,
          nextEventSeq + progressEvents.length + sourceExpansionEvents.length,
        ),
      );
      return nextEventSeq + progressEvents.length + sourceExpansionEvents.length + 1;
    }
    case "run_complete": {
      const completedAt = toIsoTimestamp(event.data.completedAt);
      ingestRunHistoryEvent(
        store,
        createRunProgressEvent(
          event.data.runId,
          nextEventSeq,
          "research_verification_started",
          completedAt,
          {
            stage: "verification",
            message: "Validating retrieval evidence before final synthesis.",
          },
          {
            sourceCount: event.data.sources.length,
          },
        ),
      );
      ingestRunHistoryEvent(
        store,
        createRunProgressEvent(
          event.data.runId,
          nextEventSeq + 1,
          "research_synthesis_started",
          completedAt,
          {
            stage: "synthesis",
            message: "Synthesizing collected evidence into the final answer.",
          },
          {
            sourceCount: event.data.sources.length,
          },
        ),
      );
      ingestRunHistoryEvent(
        store,
        createRunCompletionEvent(
          event.data.runId,
          nextEventSeq + 2,
          "final_answer_generated",
          completedAt,
          event.data.finalAnswer,
          event.data.structuredAnswer,
          event.data.sources,
        ),
      );
      ingestRunHistoryEvent(
        store,
        createRunCompletionEvent(
          event.data.runId,
          nextEventSeq + 3,
          "run_completed",
          completedAt,
          event.data.finalAnswer,
          event.data.structuredAnswer,
          event.data.sources,
        ),
      );
      return nextEventSeq + 4;
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

function createCanonicalRetrievalActionEvent(
  event: RetrievalActionEvent,
  eventSeq: number,
): CanonicalRunEvent {
  const timestamp =
    event.status === "started"
      ? event.startedAt ?? Date.now()
      : event.endedAt ?? event.startedAt ?? Date.now();
  const retrievalAction = createCanonicalRetrievalActionMetadata(event);

  if (event.status === "completed") {
    return {
      run_id: event.runId,
      event_seq: eventSeq,
      event_type: "retrieval_action_succeeded",
      ts: toIsoTimestamp(timestamp),
      retrieval_action: retrievalAction,
      tool_output: createRetrievalActionOutputPayload(event),
      safety: createEmptyRunEventSafety(),
    };
  }

  if (event.status === "failed") {
    return {
      run_id: event.runId,
      event_seq: eventSeq,
      event_type: "retrieval_action_failed",
      ts: toIsoTimestamp(timestamp),
      retrieval_action: retrievalAction,
      tool_input: createRetrievalActionInputPayload(event),
      error_output: {
        message: event.error ?? "Retrieval action failed.",
      },
      safety: createEmptyRunEventSafety(),
    };
  }

  return {
    run_id: event.runId,
    event_seq: eventSeq,
    event_type: "retrieval_action_started",
    ts: toIsoTimestamp(timestamp),
    retrieval_action: retrievalAction,
    tool_input: createRetrievalActionInputPayload(event),
    safety: createEmptyRunEventSafety(),
  };
}

function createRunProgressEvent(
  runId: string,
  eventSeq: number,
  eventType:
    | "research_planning_started"
    | "research_search_started"
    | "research_crawl_started"
    | "research_verification_started"
    | "research_sources_expanded"
    | "research_synthesis_started",
  timestamp: string,
  progress: NonNullable<CanonicalRunEvent["progress"]>,
  payload?: CanonicalRunEvent["tool_input"] | CanonicalRunEvent["tool_output"],
): CanonicalRunEvent {
  if (
    eventType === "research_planning_started" ||
    eventType === "research_search_started" ||
    eventType === "research_crawl_started"
  ) {
    return {
      run_id: runId,
      event_seq: eventSeq,
      event_type: eventType,
      ts: timestamp,
      progress,
      ...(payload !== undefined ? { tool_input: payload } : {}),
      safety: createEmptyRunEventSafety(),
    };
  }

  return {
    run_id: runId,
    event_seq: eventSeq,
    event_type: eventType,
    ts: timestamp,
    progress,
    ...(payload !== undefined ? { tool_output: payload } : {}),
    safety: createEmptyRunEventSafety(),
  };
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

function createRetrievalProgressEvents(
  event: RetrievalActionEvent,
  nextEventSeq: number,
): CanonicalRunEvent[] {
  if (event.status !== "started") {
    return [];
  }

  const timestamp = toIsoTimestamp(event.startedAt ?? Date.now());

  switch (event.actionType) {
    case "search":
      return [
        createRunProgressEvent(
          event.runId,
          nextEventSeq,
          "research_search_started",
          timestamp,
          {
            stage: "search",
            message: `Searching and reranking sources for "${event.query}".`,
          },
          createRetrievalActionInputPayload(event),
        ),
      ];
    case "open_page":
      return [
        createRunProgressEvent(
          event.runId,
          nextEventSeq,
          "research_crawl_started",
          timestamp,
          {
            stage: "crawl",
            message: "Selecting an objective-driven page crawl.",
          },
          createRetrievalActionInputPayload(event),
        ),
      ];
    case "find_in_page":
      return [
        createRunProgressEvent(
          event.runId,
          nextEventSeq,
          "research_verification_started",
          timestamp,
          {
            stage: "verification",
            message: `Checking evidence for "${event.pattern}" within the opened page.`,
          },
          createRetrievalActionInputPayload(event),
        ),
      ];
  }
}

function createToolProgressEvents(
  event: ToolCallEvent,
  nextEventSeq: number,
): CanonicalRunEvent[] {
  if (event.status !== "started") {
    return [];
  }

  const timestamp = toIsoTimestamp(event.startedAt ?? Date.now());

  switch (event.toolName) {
    case "web_search":
      return [
        createRunProgressEvent(
          event.runId,
          nextEventSeq,
          "research_search_started",
          timestamp,
          {
            stage: "search",
            message: "Searching and reranking candidate sources.",
          },
          toPreviewPayload(event.inputPreview),
        ),
      ];
    case "open_url":
      return [
        createRunProgressEvent(
          event.runId,
          nextEventSeq,
          "research_crawl_started",
          timestamp,
          {
            stage: "crawl",
            message: "Opening selected pages for extraction.",
          },
          toPreviewPayload(event.inputPreview),
        ),
      ];
  }
}

function createSourceExpansionEvents(
  store: RunHistoryStoreLike | null,
  event: ToolCallEvent,
  nextEventSeq: number,
): CanonicalRunEvent[] {
  if (
    store === null ||
    event.toolName !== "web_search" ||
    event.status === "started" ||
    store.getRun(event.runId)?.events.some((runEvent) => {
      return runEvent.event_type === "research_sources_expanded";
    })
  ) {
    return [];
  }

  return [
    createRunProgressEvent(
      event.runId,
      nextEventSeq,
      "research_sources_expanded",
      toIsoTimestamp(event.endedAt ?? event.startedAt ?? Date.now()),
      {
        stage: "source_expansion",
        message: "Collecting broad coverage from search before targeted crawling.",
      },
      toPreviewPayload(event.outputPreview),
    ),
  ];
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

function createCanonicalRetrievalActionMetadata(event: RetrievalActionEvent) {
  return {
    action_id: event.actionId,
    action_type: event.actionType,
    ...(event.actionType === "search" ? { query: event.query } : {}),
    ...(event.actionType === "open_page" ? { url: event.url } : {}),
    ...(event.actionType === "find_in_page"
      ? {
          url: event.url,
          pattern: event.pattern,
        }
      : {}),
    ...(event.resultCount !== undefined ? { result_count: event.resultCount } : {}),
    ...(event.matchCount !== undefined ? { match_count: event.matchCount } : {}),
  };
}

function createRetrievalActionInputPayload(
  event: RetrievalActionEvent,
): Record<string, string> | undefined {
  switch (event.actionType) {
    case "search":
      return {
        query: event.query,
        ...(event.inputPreview !== undefined ? { preview: event.inputPreview } : {}),
      };
    case "open_page":
      return {
        url: event.url,
        ...(event.inputPreview !== undefined ? { preview: event.inputPreview } : {}),
      };
    case "find_in_page":
      return {
        url: event.url,
        pattern: event.pattern,
        ...(event.inputPreview !== undefined ? { preview: event.inputPreview } : {}),
      };
  }
}

function createRetrievalActionOutputPayload(
  event: RetrievalActionEvent,
): Record<string, string | number> | undefined {
  const payload: Record<string, string | number> = {};

  if (event.outputPreview !== undefined) {
    payload.preview = event.outputPreview;
  }

  if (event.title !== undefined) {
    payload.title = event.title;
  }

  if (event.resultCount !== undefined) {
    payload.result_count = event.resultCount;
  }

  if (event.matchCount !== undefined) {
    payload.match_count = event.matchCount;
  }

  return Object.keys(payload).length > 0 ? payload : undefined;
}

function createRunCompletionEvent(
  runId: string,
  eventSeq: number,
  eventType: "final_answer_generated" | "run_completed",
  timestamp: string,
  finalAnswer: string,
  structuredAnswer: StructuredAnswer | undefined,
  sources: RunSource[],
): CanonicalRunEvent {
  const toolOutput = createCompletionToolOutput(structuredAnswer, sources);

  return {
    run_id: runId,
    event_seq: eventSeq,
    event_type: eventType,
    ts: timestamp,
    final_answer: finalAnswer,
    ...(toolOutput !== undefined ? { tool_output: toolOutput } : {}),
    safety: createEmptyRunEventSafety(),
  };
}

function createCompletionToolOutput(
  structuredAnswer: StructuredAnswer | undefined,
  sources: RunSource[],
): NonNullable<CanonicalRunEvent["tool_output"]> | undefined {
  if (structuredAnswer === undefined && sources.length === 0) {
    return undefined;
  }

  return {
    ...(structuredAnswer !== undefined ? { answer: structuredAnswer } : {}),
    ...(sources.length > 0 ? { sources } : {}),
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
      code: code ?? DEFAULT_RUN_FAILED_CODE,
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

function getPlanningMessage(mode: RunMode): string {
  switch (mode) {
    case "quick":
      return "Starting a fast search pass for a concise answer.";
    case "agentic":
      return "Building an exploratory research plan and selecting retrieval paths.";
    case "deep_research":
      return "Preparing a longer background research plan with broader source expansion.";
  }
}

function createRunNotFoundEvent(runId: string): RunStreamEvent {
  return createRunErrorEvent(
    runId,
    "Run was not found or has already been consumed.",
    "RUN_NOT_FOUND",
  );
}

function createRunStreamUnavailableEvent(runId: string): RunStreamEvent {
  return createRunErrorEvent(
    runId,
    "Run event stream is unavailable.",
    "STREAM_UNAVAILABLE",
  );
}

function createRunStreamFailureEvent(
  runId: string,
  error: unknown = undefined,
): RunStreamEvent {
  return createRunErrorEvent(
    runId,
    error instanceof Error ? error.message : "Run event stream failed.",
    "STREAM_FAILURE",
  );
}

function createRunExecutionFailureEvent(
  runId: string,
  error: unknown,
): RunStreamEvent {
  return createRunErrorEvent(
    runId,
    error instanceof Error ? error.message : "Run execution failed.",
    "RUN_EXECUTION_FAILED",
  );
}

function createRunResultFailureEvent(
  runId: string,
  result: Extract<RunExecutorResult, { status: "failed" }>,
): RunStreamEvent {
  return createRunErrorEvent(
    runId,
    result.message,
    result.code ?? DEFAULT_RUN_FAILED_CODE,
    result.failedAt ?? Date.now(),
  );
}

function createRunCompleteData(
  runId: string,
  result: Extract<RunExecutorResult, { status: "completed" }>,
) {
  return {
    runId,
    finalAnswer: result.finalAnswer,
    ...(result.structuredAnswer !== undefined
      ? { structuredAnswer: result.structuredAnswer }
      : {}),
    sources: result.sources,
    completedAt: result.completedAt ?? Date.now(),
    durationMs: result.durationMs ?? 0,
  };
}

function createRunExecutorContext(
  runId: string,
  signal: AbortSignal,
  run: PendingRun,
): RunExecutorContext {
  return {
    runId,
    signal,
    prompt: run.prompt,
    mode: run.mode,
    retrievalPolicy: run.retrievalPolicy,
  };
}

function createRunExecutorEvent(
  runId: string,
  result: RunExecutorResult,
): RunStreamEvent {
  if (result.status === "completed") {
    return {
      event: "run_complete",
      data: createRunCompleteData(runId, result),
    };
  }

  return createRunResultFailureEvent(runId, result);
}

function createRunningState(runId: string) {
  return {
    runId,
    state: "running" as const,
    ts: Date.now(),
  };
}

function createRunningRunStateEvent(runId: string): RunStreamEvent {
  return {
    event: "run_state",
    data: createRunningState(runId),
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

function serializeSearchPolicy(searchPolicy: RunRetrievalPolicy["search"]) {
  return {
    country: searchPolicy.country,
    language: searchPolicy.language,
    freshness: searchPolicy.freshness,
    domainScope: serializeDomainScope(searchPolicy.domainScope),
  };
}

function serializeDomainScope(domainScope: RunRetrievalPolicy["search"]["domainScope"]) {
  return {
    includeDomains: [...domainScope.includeDomains],
    excludeDomains: [...domainScope.excludeDomains],
  };
}

function serializeBackendSearchPolicy(searchPolicy: RunRetrievalPolicy["search"]) {
  return {
    country: searchPolicy.country,
    language: searchPolicy.language,
    freshness: searchPolicy.freshness,
    ...serializeBackendDomainScope(searchPolicy.domainScope),
  };
}

function serializeBackendDomainScope(
  domainScope: RunRetrievalPolicy["search"]["domainScope"],
) {
  return {
    include_domains: [...domainScope.includeDomains],
    exclude_domains: [...domainScope.excludeDomains],
  };
}

function serializeFetchPolicy(fetchPolicy: RunRetrievalPolicy["fetch"]) {
  return {
    maxAgeMs: fetchPolicy.maxAgeMs,
    fresh: fetchPolicy.fresh,
  };
}

function serializeBackendFetchPolicy(fetchPolicy: RunRetrievalPolicy["fetch"]) {
  return {
    max_age_ms: fetchPolicy.maxAgeMs,
    fresh: fetchPolicy.fresh,
  };
}

function serializeRunStreamEvent(event: unknown): string {
  const parsed = parseRunStreamEvent(event);
  return `event: ${parsed.event}\ndata: ${JSON.stringify(parsed.data)}\n\n`;
}

function createRunStartRateLimitEnvelope(input: {
  request: PendingRun;
  startedAt: number;
  message: string;
}) {
  return {
    ok: false as const,
    operation: "run_start" as const,
    durationMs: Math.max(0, Date.now() - input.startedAt),
    request: {
      prompt: input.request.prompt,
      mode: input.request.mode,
      retrievalPolicy: input.request.retrievalPolicy,
    },
    error: {
      code: "RATE_LIMITED" as const,
      message: input.message,
      details: {
        kind: "rate_limited",
        retryable: true,
      },
    },
  };
}
