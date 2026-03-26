import {
  parseRunStreamEvent,
  type RunMode,
  type RunCompleteEvent,
  type RunErrorEvent,
  type RetrievalActionEvent,
  type RunStateEvent,
  type RunStreamEvent,
  type ToolCallEvent,
} from "./browser-contracts.js";

export interface RunStartRequest {
  prompt: string;
  mode: RunMode;
  threadId?: string;
}

export interface RunStartResponse {
  runId: string;
  status: "queued" | "running";
}

interface RunStartErrorEnvelope {
  ok: false;
  operation: "run_start";
  durationMs: number;
  request: RunStartRequest | null;
  error: {
    code: string;
    message: string;
  };
}

export interface RunStartSuccessResult {
  ok: true;
  data: RunStartResponse;
}

export interface RunStartFailureResult {
  ok: false;
  message: string;
}

export type RunStartResult = RunStartSuccessResult | RunStartFailureResult;

export interface RunStreamSubscription {
  close(): void;
}

export interface RunStreamHandlers {
  onOpen?: () => void;
  onRunState?: (event: RunStateEvent) => void;
  onRetrievalAction?: (event: RetrievalActionEvent) => void;
  onToolCall?: (event: ToolCallEvent) => void;
  onRunComplete?: (event: RunCompleteEvent) => void;
  onRunError?: (event: RunErrorEvent) => void;
  onInvalidEvent?: (message: string, cause?: unknown) => void;
  onTransportError?: () => void;
}

export interface EventSourceLike {
  addEventListener(
    type: string,
    listener: (event: Event | MessageEvent<string>) => void,
  ): void;
  removeEventListener(
    type: string,
    listener: (event: Event | MessageEvent<string>) => void,
  ): void;
  close(): void;
}

export interface RunStreamSubscriptionOptions {
  eventSourceFactory?: (url: string) => EventSourceLike;
}

let activeRunStream: RunStreamSubscription | null = null;
const RUN_MODES: ReadonlySet<RunMode> = new Set([
  "quick",
  "agentic",
]);

export async function createRun(request: RunStartRequest): Promise<RunStartResult> {
  try {
    const response = await fetch("/api/runs", {
      method: "POST",
      headers: {
        "content-type": "application/json",
      },
      body: JSON.stringify(request),
    });

    const payload: unknown = await response.json();

    if (response.ok) {
      return {
        ok: true,
        data: parseRunStartResponse(payload),
      };
    }

    const envelope = parseRunStartErrorEnvelope(payload);
    return {
      ok: false,
      message: envelope.error.message,
    };
  } catch (error: unknown) {
    return {
      ok: false,
      message:
        error instanceof Error
          ? error.message
          : "Failed to start run.",
    };
  }
}

export function subscribeToRunEvents(
  runId: string,
  handlers: RunStreamHandlers,
  options: RunStreamSubscriptionOptions = {},
): RunStreamSubscription {
  activeRunStream?.close();

  const createEventSource = options.eventSourceFactory ?? defaultEventSourceFactory;
  const eventSource = createEventSource(
    `/api/runs/${encodeURIComponent(runId)}/events`,
  );
  let closed = false;

  const close = () => {
    if (closed) {
      return;
    }

    closed = true;
    for (const [eventName, listener] of Object.entries(listeners)) {
      eventSource.removeEventListener(eventName, listener);
    }
    eventSource.close();

    if (activeRunStream === subscription) {
      activeRunStream = null;
    }
  };

  const handleParsedEvent = (event: RunStreamEvent) => {
    switch (event.event) {
      case "run_state":
        handlers.onRunState?.(event.data);
        return;
      case "retrieval_action":
        handlers.onRetrievalAction?.(event.data);
        return;
      case "tool_call":
        handlers.onToolCall?.(event.data);
        return;
      case "run_complete":
        handlers.onRunComplete?.(event.data);
        close();
        return;
      case "run_error":
        handlers.onRunError?.(event.data);
        close();
        return;
    }
  };

  const parseAndHandleEvent = (
    eventName: RunStreamEvent["event"],
    rawEvent: Event | MessageEvent<string>,
  ) => {
    if (!("data" in rawEvent) || typeof rawEvent.data !== "string") {
      handlers.onInvalidEvent?.(`Run event ${eventName} was missing a data payload.`);
      return;
    }

    try {
      const parsed = parseRunStreamEvent({
        event: eventName,
        data: JSON.parse(rawEvent.data),
      });
      handleParsedEvent(parsed);
    } catch (error: unknown) {
      handlers.onInvalidEvent?.(
        `Run event ${eventName} failed validation.`,
        error,
      );
    }
  };

  const listeners = {
    open: () => {
      handlers.onOpen?.();
    },
    error: () => {
      handlers.onTransportError?.();
    },
    run_state: (event: Event | MessageEvent<string>) => {
      parseAndHandleEvent("run_state", event);
    },
    retrieval_action: (event: Event | MessageEvent<string>) => {
      parseAndHandleEvent("retrieval_action", event);
    },
    tool_call: (event: Event | MessageEvent<string>) => {
      parseAndHandleEvent("tool_call", event);
    },
    run_complete: (event: Event | MessageEvent<string>) => {
      parseAndHandleEvent("run_complete", event);
    },
    run_error: (event: Event | MessageEvent<string>) => {
      parseAndHandleEvent("run_error", event);
    },
  } satisfies Record<
    "open" | "error" | RunStreamEvent["event"],
    (event: Event | MessageEvent<string>) => void
  >;

  for (const [eventName, listener] of Object.entries(listeners)) {
    eventSource.addEventListener(eventName, listener);
  }

  const subscription = { close };
  activeRunStream = subscription;
  return subscription;
}

function parseRunStartResponse(input: unknown): RunStartResponse {
  const record = asRecord(input);
  if (
    typeof record.runId !== "string" ||
    (record.status !== "queued" && record.status !== "running")
  ) {
    throw new Error("Run start response failed validation.");
  }

  return {
    runId: record.runId,
    status: record.status,
  };
}

function defaultEventSourceFactory(url: string): EventSourceLike {
  return new EventSource(url);
}

function parseRunStartErrorEnvelope(input: unknown): RunStartErrorEnvelope {
  const record = asRecord(input);
  const error = asRecord(record.error);

  if (
    record.ok !== false ||
    record.operation !== "run_start" ||
    typeof record.durationMs !== "number" ||
    (record.request !== null && !isRunStartRequest(record.request)) ||
    typeof error.code !== "string" ||
    typeof error.message !== "string"
  ) {
    throw new Error("Run start error response failed validation.");
  }

  return {
    ok: false,
    operation: "run_start",
    durationMs: record.durationMs,
    request: record.request ?? null,
    error: {
      code: error.code,
      message: error.message,
    },
  };
}

function isRunStartRequest(input: unknown): input is RunStartRequest {
  const record = asRecord(input);
  return (
    typeof record.prompt === "string" &&
    isRunMode(record.mode)
  );
}

function asRecord(input: unknown): Record<string, unknown> {
  if (typeof input !== "object" || input === null || Array.isArray(input)) {
    return {};
  }

  return input as Record<string, unknown>;
}

function isRunMode(input: unknown): input is RunMode {
  return typeof input === "string" && RUN_MODES.has(input as RunMode);
}
