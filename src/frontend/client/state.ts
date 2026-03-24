import type { RunStartResponse } from "./api-client.js";
import {
  type CanonicalRunProgress,
  type CanonicalRunEvent,
  type RunCompleteEvent,
  type RunErrorEvent,
  type RetrievalActionEvent,
  type RunStateEvent,
  type ToolCallEvent,
  type RunMode,
  createRunEventKey,
} from "./browser-contracts.js";

export type RunPhase = "idle" | "starting" | "running" | "completed" | "failed";
type DraftRunEvent = Omit<CanonicalRunEvent, "event_seq" | "safety">;
type AppendableRunEvent = DraftRunEvent & {
  safety?: CanonicalRunEvent["safety"];
};
type RunEventStateSlice = Pick<RunState, "runEvents" | "selectedEventKey" | "nextEventSeq">;
type ResettableRunStateFields = Pick<
  RunState,
  | "phase"
  | "activeRunId"
  | "error"
  | "finalAnswer"
  | "completedAt"
  | "toolCalls"
  | "runEvents"
  | "selectedEventKey"
  | "nextEventSeq"
>;

export interface ToolCallRecord {
  toolCallId: string;
  toolName: ToolCallEvent["toolName"];
  status: ToolCallEvent["status"];
  startedAt: number | null;
  endedAt: number | null;
  durationMs: number | null;
  inputPreview: string | null;
  outputPreview: string | null;
  error: string | null;
  sortTimestamp: number;
  updatedAt: number;
}

export interface RunState {
  phase: RunPhase;
  prompt: string;
  selectedMode: RunMode;
  activeRunId: string | null;
  error: string | null;
  finalAnswer: string | null;
  completedAt: number | null;
  toolCalls: ToolCallRecord[];
  runEvents: CanonicalRunEvent[];
  selectedEventKey: string | null;
  nextEventSeq: number;
}

export type RunAction =
  | { type: "prompt_updated"; prompt: string }
  | { type: "mode_updated"; mode: RunMode }
  | { type: "run_requested" }
  | { type: "run_started"; response: RunStartResponse }
  | { type: "run_failed"; message: string }
  | { type: "run_state_received"; event: RunStateEvent }
  | { type: "retrieval_action_received"; event: RetrievalActionEvent }
  | { type: "tool_call_received"; event: ToolCallEvent }
  | { type: "run_completed"; event: RunCompleteEvent }
  | { type: "run_error_received"; event: RunErrorEvent }
  | { type: "run_event_selected"; eventKey: string }
  | { type: "preview_events_loaded"; events: CanonicalRunEvent[] };

export const initialRunState: RunState = {
  phase: "idle",
  prompt: "",
  selectedMode: "agentic",
  activeRunId: null,
  error: null,
  finalAnswer: null,
  completedAt: null,
  toolCalls: [],
  runEvents: [],
  selectedEventKey: null,
  nextEventSeq: 0,
};

export function reduceRunState(state: RunState, action: RunAction): RunState {
  switch (action.type) {
    case "prompt_updated":
      return resetFailedState({
        ...state,
        prompt: action.prompt,
      });
    case "mode_updated":
      return resetFailedState({
        ...state,
        selectedMode: action.mode,
      });
    case "run_requested":
      if (isRunInFlight(state.phase)) {
        return state;
      }

      return createRunStateSnapshot(state, {
        phase: "starting",
      });
    case "run_started":
      if (state.phase !== "starting") {
        return state;
      }

      const startedAtIso = toIsoTimestamp();
      const runInput = createRunInputPayload(state);
      return {
        ...state,
        phase: "running",
        activeRunId: action.response.runId,
        error: null,
        finalAnswer: null,
        completedAt: null,
        toolCalls: [],
        ...appendRunEvents(
          state,
          createRunStartedEvents(
            action.response.runId,
            state.selectedMode,
            startedAtIso,
            runInput,
          ),
        ),
      };
    case "run_failed":
      if (
        state.phase === "running" ||
        state.phase === "completed" ||
        state.phase === "failed"
      ) {
        return state;
      }

      return createRunStateSnapshot(state, {
        phase: "failed",
        error: action.message,
      });
    case "run_state_received":
      if (shouldIgnoreRunUpdate(state, action.event.runId)) {
        return state;
      }

      switch (action.event.state) {
        case "queued":
          return state;
        case "running":
          return {
            ...state,
            phase: "running",
          };
        case "completed":
          return {
            ...state,
            phase: "completed",
            completedAt: action.event.ts,
          };
        case "failed":
          return {
            ...state,
            phase: "failed",
            completedAt: action.event.ts,
            error: state.error ?? "Run failed.",
          };
      }
    case "retrieval_action_received":
      if (shouldIgnoreRunUpdate(state, action.event.runId)) {
        return state;
      }

      return {
        ...state,
        phase: "running",
        ...appendRunEvents(state, [
          ...createRetrievalProgressEvents(action.event),
          createCanonicalRetrievalEvent(action.event),
        ]),
      };
    case "tool_call_received":
      if (shouldIgnoreRunUpdate(state, action.event.runId)) {
        return state;
      }

      return {
        ...state,
        phase: "running",
        toolCalls: mergeToolCall(state.toolCalls, action.event),
        ...appendRunEvents(state, [
          ...createToolProgressEvents(action.event),
          ...createSourceExpansionEvents(state, action.event),
          createCanonicalToolEvent(action.event),
        ]),
      };
    case "run_completed":
      if (shouldIgnoreRunUpdate(state, action.event.runId)) {
        return state;
      }

      const completedAtIso = toIsoTimestamp(action.event.completedAt);
      const completedToolCalls = countCompletedToolCalls(state.toolCalls);
      return {
        ...state,
        phase: "completed",
        finalAnswer: action.event.finalAnswer,
        completedAt: action.event.completedAt,
        error: null,
        ...appendRunEvents(state, [
          createResearchProgressEvent(
            action.event.runId,
            "research_verification_started",
            completedAtIso,
            {
              stage: "verification",
              message: "Validating retrieval evidence before final synthesis.",
              completed: completedToolCalls,
              total: state.toolCalls.length,
            },
            {
              toolCalls: state.toolCalls.length,
              completedToolCalls,
            },
          ),
          createResearchProgressEvent(
            action.event.runId,
            "research_synthesis_started",
            completedAtIso,
            {
              stage: "synthesis",
              message: "Synthesizing collected evidence into the final answer.",
              completed: completedToolCalls,
              total: state.toolCalls.length,
            },
            {
              toolCalls: state.toolCalls.length,
              completedToolCalls,
            },
          ),
          createRunOutcomeEvent(
            action.event.runId,
            "final_answer_generated",
            completedAtIso,
            action.event.finalAnswer,
            action.event.structuredAnswer,
            action.event.sources,
          ),
          createRunOutcomeEvent(
            action.event.runId,
            "run_completed",
            completedAtIso,
            action.event.finalAnswer,
            action.event.structuredAnswer,
            action.event.sources,
          ),
        ]),
      };
    case "run_error_received":
      if (shouldIgnoreRunUpdate(state, action.event.runId)) {
        return state;
      }

      return {
        ...state,
        phase: "failed",
        error: action.event.message,
        completedAt: action.event.failedAt,
        ...appendRunEvent(state, {
          run_id: action.event.runId,
          event_type: "run_failed",
          ts: toIsoTimestamp(action.event.failedAt),
          error_output: {
            code: action.event.code ?? "RUN_FAILED",
            message: action.event.message,
          },
        }),
      };
    case "run_event_selected":
      return {
        ...state,
        selectedEventKey: action.eventKey,
      };
    case "preview_events_loaded": {
      return {
        ...state,
        ...createRunEventStateSlice(
          [...action.events].sort(compareRunEvents),
          action.events.reduce(
            (highest, event) => Math.max(highest, event.event_seq),
            -1,
          ) + 1,
        ),
      };
    }
  }
}

function appendRunEvent(
  state: RunState,
  event: AppendableRunEvent,
): RunEventStateSlice {
  return appendRunEvents(state, [event]);
}

function appendRunEvents(
  state: RunState,
  events: AppendableRunEvent[],
): RunEventStateSlice {
  let nextEventSeq = state.nextEventSeq;
  const appended = events.map((event) => ({
    ...event,
    event_seq: nextEventSeq++,
    safety: event.safety ?? createEmptyEventSafety(),
  })) as CanonicalRunEvent[];
  return createRunEventStateSlice(
    [...state.runEvents, ...appended].sort(compareRunEvents),
    nextEventSeq,
  );
}

function createRunInputPayload(
  state: Pick<RunState, "prompt" | "selectedMode">,
): CanonicalRunEvent["tool_input"] {
  return {
    prompt: state.prompt,
    mode: state.selectedMode,
  };
}

function createRunStartedEvents(
  runId: string,
  mode: RunMode,
  timestamp: string,
  runInput: CanonicalRunEvent["tool_input"],
): DraftRunEvent[] {
  return [
    {
      run_id: runId,
      event_type: "run_started",
      ts: timestamp,
      tool_input: runInput,
    },
    createResearchProgressEvent(
      runId,
      "research_planning_started",
      timestamp,
      {
        stage: "planning",
        message: getPlanningMessage(mode),
      },
      runInput,
    ),
  ];
}

function createCanonicalToolEvent(
  event: ToolCallEvent,
): DraftRunEvent {
  switch (event.status) {
    case "started":
      return {
        ...createToolEventBase(
          event,
          "tool_call_started",
          event.startedAt ?? Date.now(),
        ),
        tool_input: createPreviewPayload(
          event.inputPreview,
          "Tool input preview unavailable.",
        ),
      };
    case "completed":
      return {
        ...createToolEventBase(
          event,
          "tool_call_succeeded",
          event.endedAt ?? Date.now(),
        ),
        tool_output: createPreviewPayload(
          event.outputPreview,
          "Tool output preview unavailable.",
        ),
      };
    case "failed":
      return {
        ...createToolEventBase(
          event,
          "tool_call_failed",
          event.endedAt ?? Date.now(),
        ),
        error_output: {
          message: event.error ?? "Tool call failed.",
        },
      };
  }
}

function createCanonicalRetrievalEvent(
  event: RetrievalActionEvent,
): DraftRunEvent {
  const timestamp =
    event.status === "started"
      ? event.startedAt ?? Date.now()
      : event.endedAt ?? event.startedAt ?? Date.now();
  const retrievalAction = createRetrievalActionMetadata(event);

  if (event.status === "completed") {
    return {
      run_id: event.runId,
      event_type: "retrieval_action_succeeded",
      ts: toIsoTimestamp(timestamp),
      retrieval_action: retrievalAction,
      tool_output: createRetrievalOutputPayload(event),
    };
  }

  if (event.status === "failed") {
    return {
      run_id: event.runId,
      event_type: "retrieval_action_failed",
      ts: toIsoTimestamp(timestamp),
      retrieval_action: retrievalAction,
      tool_input: createRetrievalInputPayload(event),
      error_output: {
        message: event.error ?? "Retrieval action failed.",
      },
    };
  }

  return {
    run_id: event.runId,
    event_type: "retrieval_action_started",
    ts: toIsoTimestamp(timestamp),
    retrieval_action: retrievalAction,
    tool_input: createRetrievalInputPayload(event),
  };
}

function createToolEventBase(
  event: ToolCallEvent,
  eventType: CanonicalRunEvent["event_type"],
  timestamp: number,
): Pick<
  CanonicalRunEvent,
  "run_id" | "event_type" | "ts" | "tool_name" | "tool_call_id"
> {
  return {
    run_id: event.runId,
    event_type: eventType,
    ts: toIsoTimestamp(timestamp),
    tool_name: event.toolName,
    tool_call_id: event.toolCallId,
  };
}

function createPreviewPayload(preview: string | undefined, fallback: string) {
  return {
    preview: preview ?? fallback,
  };
}

function createResearchProgressEvent(
  runId: string,
  eventType:
    | "research_planning_started"
    | "research_search_started"
    | "research_crawl_started"
    | "research_verification_started"
    | "research_sources_expanded"
    | "research_synthesis_started",
  timestamp: string,
  progress: CanonicalRunProgress,
  payload?: CanonicalRunEvent["tool_input"] | CanonicalRunEvent["tool_output"],
): DraftRunEvent {
  if (
    eventType === "research_planning_started" ||
    eventType === "research_search_started" ||
    eventType === "research_crawl_started"
  ) {
    return {
      run_id: runId,
      event_type: eventType,
      ts: timestamp,
      progress,
      tool_input: payload,
    };
  }

  return {
    run_id: runId,
    event_type: eventType,
    ts: timestamp,
    progress,
    tool_output: payload,
  };
}

function createSourceExpansionEvents(
  state: RunState,
  event: ToolCallEvent,
): DraftRunEvent[] {
  if (
    event.toolName !== "web_search" ||
    event.status !== "completed" ||
    hasRunEventType(state.runEvents, "research_sources_expanded")
  ) {
    return [];
  }

  return [
    createResearchProgressEvent(
      event.runId,
      "research_sources_expanded",
      toIsoTimestamp(event.startedAt ?? event.endedAt),
      {
        stage: "source_expansion",
        message: `Expanding sources with ${formatToolLabel(event.toolName)}.`,
        completed: countDistinctToolCalls(state.toolCalls, event.toolCallId),
      },
      {
        tool: event.toolName,
        preview:
          event.outputPreview ??
          event.inputPreview ??
          event.error ??
          "Research source update recorded.",
      },
    ),
  ];
}

function createToolProgressEvents(event: ToolCallEvent): DraftRunEvent[] {
  if (event.status !== "started") {
    return [];
  }

  const timestamp = toIsoTimestamp(event.startedAt ?? Date.now());

  switch (event.toolName) {
    case "web_search":
      return [
        createResearchProgressEvent(
          event.runId,
          "research_search_started",
          timestamp,
          {
            stage: "search",
            message: "Searching and reranking candidate sources.",
          },
          createPreviewPayload(
            event.inputPreview,
            "Search input preview unavailable.",
          ),
        ),
      ];
    case "open_url":
      return [
        createResearchProgressEvent(
          event.runId,
          "research_crawl_started",
          timestamp,
          {
            stage: "crawl",
            message: "Opening selected pages for extraction.",
          },
          createPreviewPayload(
            event.inputPreview,
            "Crawl input preview unavailable.",
          ),
        ),
      ];
  }
}

function createRetrievalProgressEvents(
  event: RetrievalActionEvent,
): DraftRunEvent[] {
  if (event.status !== "started") {
    return [];
  }

  const timestamp = toIsoTimestamp(event.startedAt ?? Date.now());

  switch (event.actionType) {
    case "search":
      return [
        createResearchProgressEvent(
          event.runId,
          "research_search_started",
          timestamp,
          {
            stage: "search",
            message: `Searching and reranking sources for "${event.query}".`,
          },
          createRetrievalInputPayload(event),
        ),
      ];
    case "open_page":
      return [
        createResearchProgressEvent(
          event.runId,
          "research_crawl_started",
          timestamp,
          {
            stage: "crawl",
            message: "Opening selected pages for extraction.",
          },
          createRetrievalInputPayload(event),
        ),
      ];
    case "find_in_page":
      return [
        createResearchProgressEvent(
          event.runId,
          "research_verification_started",
          timestamp,
          {
            stage: "verification",
            message: `Checking evidence for "${event.pattern}" within the opened page.`,
          },
          createRetrievalInputPayload(event),
        ),
      ];
  }
}

function createRetrievalActionMetadata(event: RetrievalActionEvent) {
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

function createRetrievalInputPayload(
  event: RetrievalActionEvent,
): CanonicalRunEvent["tool_input"] | undefined {
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

function createRetrievalOutputPayload(
  event: RetrievalActionEvent,
): CanonicalRunEvent["tool_output"] | undefined {
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

function createRunOutcomeEvent(
  runId: string,
  eventType: "final_answer_generated" | "run_completed",
  timestamp: string,
  finalAnswer: string,
  structuredAnswer: RunCompleteEvent["structuredAnswer"],
  sources: RunCompleteEvent["sources"],
): DraftRunEvent {
  const toolOutput = createCompletionToolOutput(structuredAnswer, sources);

  return {
    run_id: runId,
    event_type: eventType,
    ts: timestamp,
    final_answer: finalAnswer,
    ...(toolOutput !== undefined ? { tool_output: toolOutput } : {}),
  };
}

function compareRunEvents(left: CanonicalRunEvent, right: CanonicalRunEvent): number {
  if (left.run_id !== right.run_id) {
    return left.run_id.localeCompare(right.run_id);
  }

  return left.event_seq - right.event_seq;
}

function createRunStateSnapshot(
  state: RunState,
  overrides: Partial<ResettableRunStateFields>,
): RunState {
  return {
    ...state,
    activeRunId: null,
    error: null,
    finalAnswer: null,
    completedAt: null,
    toolCalls: [],
    runEvents: [],
    selectedEventKey: null,
    nextEventSeq: 0,
    ...overrides,
  };
}

function createRunEventStateSlice(
  runEvents: CanonicalRunEvent[],
  nextEventSeq: number,
): RunEventStateSlice {
  const selectedEvent = runEvents[runEvents.length - 1] ?? null;
  return {
    runEvents,
    selectedEventKey: selectedEvent ? createRunEventKey(selectedEvent) : null,
    nextEventSeq,
  };
}

function createCompletionToolOutput(
  structuredAnswer: RunCompleteEvent["structuredAnswer"],
  sources: RunCompleteEvent["sources"],
): NonNullable<CanonicalRunEvent["tool_output"]> | undefined {
  if (structuredAnswer === undefined && sources.length === 0) {
    return undefined;
  }

  return {
    ...(structuredAnswer !== undefined ? { answer: structuredAnswer } : {}),
    ...(sources.length > 0 ? { sources } : {}),
  };
}

function hasRunEventType(
  events: CanonicalRunEvent[],
  eventType: CanonicalRunEvent["event_type"],
): boolean {
  return events.some((event) => event.event_type === eventType);
}

function countDistinctToolCalls(toolCalls: ToolCallRecord[], nextToolCallId: string): number {
  return new Set([...toolCalls.map((toolCall) => toolCall.toolCallId), nextToolCallId]).size;
}

function formatToolLabel(toolName: ToolCallEvent["toolName"]): string {
  switch (toolName) {
    case "web_search":
      return "web search";
    case "open_url":
      return "open url";
  }
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

function resetFailedState(state: RunState): RunState {
  if (state.phase !== "failed") {
    return state;
  }

  return {
    ...state,
    phase: "idle",
    error: null,
  };
}

function countCompletedToolCalls(toolCalls: ToolCallRecord[]): number {
  return toolCalls.filter((toolCall) => toolCall.status === "completed").length;
}

function toIsoTimestamp(timestamp: number = Date.now()): string {
  return new Date(timestamp).toISOString();
}

function createEmptyEventSafety(): CanonicalRunEvent["safety"] {
  return {
    tool_input: createEmptyPayloadSafety(),
    tool_output: createEmptyPayloadSafety(),
    error_output: createEmptyPayloadSafety(),
  };
}

function createEmptyPayloadSafety(): CanonicalRunEvent["safety"]["tool_input"] {
  return {
    redaction: {
      active: false,
      paths: [],
    },
    truncation: {
      active: false,
      paths: [],
    },
  };
}

function mergeToolCall(
  toolCalls: ToolCallRecord[],
  event: ToolCallEvent,
): ToolCallRecord[] {
  const existing = toolCalls.find((toolCall) => toolCall.toolCallId === event.toolCallId);
  const nextRecord = mergeToolCallRecord(existing, event);

  const nextToolCalls = existing === undefined
    ? [...toolCalls, nextRecord]
    : toolCalls.map((toolCall) =>
        toolCall.toolCallId === event.toolCallId ? nextRecord : toolCall,
      );

  return [...nextToolCalls].sort(compareToolCalls);
}

function mergeToolCallRecord(
  existing: ToolCallRecord | undefined,
  event: ToolCallEvent,
): ToolCallRecord {
  const incomingStatusRank = getToolStatusRank(event.status);
  const existingStatus = existing?.status;
  const existingStatusRank =
    existingStatus === undefined ? -1 : getToolStatusRank(existingStatus);
  const status = (
    incomingStatusRank >= existingStatusRank || existingStatus === undefined
      ? event.status
      : existingStatus
  );

  const startedAt = minDefined(existing?.startedAt ?? null, event.startedAt);
  const endedAt = maxDefined(existing?.endedAt ?? null, event.endedAt);
  const durationMs =
    endedAt !== null
      ? maxDefined(existing?.durationMs ?? null, event.durationMs)
      : null;
  const sortTimestamp = minDefined(
    existing?.sortTimestamp ?? null,
    event.startedAt ?? event.endedAt,
  ) ?? 0;
  const updatedAt = maxDefined(
    existing?.updatedAt ?? null,
    event.endedAt ?? event.startedAt,
  ) ?? sortTimestamp;

  return {
    toolCallId: event.toolCallId,
    toolName: existing?.toolName ?? event.toolName,
    status,
    startedAt,
    endedAt,
    durationMs,
    inputPreview: coalesceString(existing?.inputPreview ?? null, event.inputPreview),
    outputPreview: coalesceString(existing?.outputPreview ?? null, event.outputPreview),
    error: coalesceString(existing?.error ?? null, event.error),
    sortTimestamp,
    updatedAt,
  };
}

function compareToolCalls(left: ToolCallRecord, right: ToolCallRecord): number {
  if (left.sortTimestamp !== right.sortTimestamp) {
    return left.sortTimestamp - right.sortTimestamp;
  }

  return left.toolCallId.localeCompare(right.toolCallId);
}

function getToolStatusRank(status: ToolCallEvent["status"]): number {
  switch (status) {
    case "started":
      return 0;
    case "completed":
      return 1;
    case "failed":
      return 2;
  }
}

function isTerminalPhase(phase: RunPhase): boolean {
  return phase === "completed" || phase === "failed";
}

function isRunInFlight(phase: RunPhase): boolean {
  return phase === "starting" || phase === "running";
}

function isActiveRunEvent(state: RunState, runId: string): boolean {
  return state.activeRunId !== null && state.activeRunId === runId;
}

function shouldIgnoreRunUpdate(state: RunState, runId: string): boolean {
  return !isActiveRunEvent(state, runId) || isTerminalPhase(state.phase);
}

function minDefined(
  current: number | null,
  incoming: number | undefined,
): number | null {
  if (incoming === undefined) {
    return current;
  }

  if (current === null) {
    return incoming;
  }

  return Math.min(current, incoming);
}

function maxDefined(
  current: number | null,
  incoming: number | undefined,
): number | null {
  if (incoming === undefined) {
    return current;
  }

  if (current === null) {
    return incoming;
  }

  return Math.max(current, incoming);
}

function coalesceString(
  current: string | null,
  incoming: string | undefined,
): string | null {
  if (incoming === undefined || incoming.length === 0) {
    return current;
  }

  return incoming;
}
