import type { RunStartResponse } from "./api-client.js";
import {
  type CanonicalRunProgress,
  type CanonicalRunEvent,
  type RunCompleteEvent,
  type RunErrorEvent,
  type RunStateEvent,
  type ToolCallEvent,
  createRunEventKey,
} from "../contracts.js";

export type RunPhase = "idle" | "starting" | "running" | "completed" | "failed";

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
  | { type: "run_requested" }
  | { type: "run_started"; response: RunStartResponse }
  | { type: "run_failed"; message: string }
  | { type: "run_state_received"; event: RunStateEvent }
  | { type: "tool_call_received"; event: ToolCallEvent }
  | { type: "run_completed"; event: RunCompleteEvent }
  | { type: "run_error_received"; event: RunErrorEvent }
  | { type: "run_event_selected"; eventKey: string }
  | { type: "preview_events_loaded"; events: CanonicalRunEvent[] };

export const initialRunState: RunState = {
  phase: "idle",
  prompt: "",
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
      return {
        ...state,
        prompt: action.prompt,
        ...(state.phase === "failed" ? { phase: "idle", error: null } : {}),
      };
    case "run_requested":
      if (
        state.phase === "starting" ||
        state.phase === "running"
      ) {
        return state;
      }

      return {
        ...state,
        phase: "starting",
        activeRunId: null,
        error: null,
        finalAnswer: null,
        completedAt: null,
        toolCalls: [],
        runEvents: [],
        selectedEventKey: null,
        nextEventSeq: 0,
      };
    case "run_started":
      if (state.phase !== "starting") {
        return state;
      }

      return {
        ...state,
        phase: "running",
        activeRunId: action.response.runId,
        error: null,
        finalAnswer: null,
        completedAt: null,
        toolCalls: [],
        ...appendRunEvents(state, [
          {
            run_id: action.response.runId,
            event_type: "run_started",
            ts: new Date().toISOString(),
            tool_input: {
              prompt: state.prompt,
            },
          },
          createResearchProgressEvent(
            action.response.runId,
            "research_planning_started",
            new Date().toISOString(),
            {
              stage: "planning",
              message: "Building an initial research plan and selecting retrieval paths.",
            },
            {
              prompt: state.prompt,
            },
          ),
        ]),
      };
    case "run_failed":
      if (
        state.phase === "running" ||
        state.phase === "completed" ||
        state.phase === "failed"
      ) {
        return state;
      }

      return {
        ...state,
        phase: "failed",
        activeRunId: null,
        error: action.message,
        finalAnswer: null,
        completedAt: null,
        toolCalls: [],
        runEvents: [],
        selectedEventKey: null,
        nextEventSeq: 0,
      };
    case "run_state_received":
      if (!isActiveRunEvent(state, action.event.runId) || isTerminalPhase(state.phase)) {
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
    case "tool_call_received":
      if (!isActiveRunEvent(state, action.event.runId) || isTerminalPhase(state.phase)) {
        return state;
      }

      const sourceExpansionEvent = hasRunEventType(
        state.runEvents,
        "research_sources_expanded",
      )
        ? []
        : [
            createResearchProgressEvent(
              action.event.runId,
              "research_sources_expanded",
              new Date(
                action.event.startedAt ??
                  action.event.endedAt ??
                  Date.now(),
              ).toISOString(),
              {
                stage: "source_expansion",
                message: `Expanding sources with ${formatToolLabel(action.event.toolName)}.`,
                completed: countDistinctToolCalls(state.toolCalls, action.event.toolCallId),
              },
              action.event.status === "started"
                ? undefined
                : {
                    tool: action.event.toolName,
                    preview:
                      action.event.outputPreview ??
                      action.event.inputPreview ??
                      action.event.error ??
                      "Research source update recorded.",
                  },
            ),
          ];

      return {
        ...state,
        phase: "running",
        toolCalls: mergeToolCall(state.toolCalls, action.event),
        ...appendRunEvents(state, [
          ...sourceExpansionEvent,
          createCanonicalToolEvent(action.event),
        ]),
      };
    case "run_completed":
      if (!isActiveRunEvent(state, action.event.runId) || isTerminalPhase(state.phase)) {
        return state;
      }

      return {
        ...state,
        phase: "completed",
        finalAnswer: action.event.finalAnswer,
        completedAt: action.event.completedAt,
        error: null,
        ...appendRunEvents(state, [
          createResearchProgressEvent(
            action.event.runId,
            "research_synthesis_started",
            new Date(action.event.completedAt).toISOString(),
            {
              stage: "synthesis",
              message: "Synthesizing collected evidence into the final answer.",
              completed: state.toolCalls.filter((toolCall) => toolCall.status === "completed").length,
              total: state.toolCalls.length,
            },
            {
              toolCalls: state.toolCalls.length,
              completedToolCalls: state.toolCalls.filter((toolCall) => toolCall.status === "completed").length,
            },
          ),
          {
            run_id: action.event.runId,
            event_type: "final_answer_generated",
            ts: new Date(action.event.completedAt).toISOString(),
            final_answer: action.event.finalAnswer,
            ...(action.event.sources.length > 0
              ? { tool_output: { sources: action.event.sources } }
              : {}),
          },
          {
            run_id: action.event.runId,
            event_type: "run_completed",
            ts: new Date(action.event.completedAt).toISOString(),
            final_answer: action.event.finalAnswer,
            ...(action.event.sources.length > 0
              ? { tool_output: { sources: action.event.sources } }
              : {}),
          },
        ]),
      };
    case "run_error_received":
      if (!isActiveRunEvent(state, action.event.runId) || isTerminalPhase(state.phase)) {
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
          ts: new Date(action.event.failedAt).toISOString(),
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
      const runEvents = [...action.events].sort(compareRunEvents);
      const selectedEvent = runEvents[runEvents.length - 1] ?? null;
      return {
        ...state,
        runEvents,
        selectedEventKey: selectedEvent ? createRunEventKey(selectedEvent) : null,
        nextEventSeq:
          action.events.reduce(
            (highest, event) => Math.max(highest, event.event_seq),
            -1,
          ) + 1,
      };
    }
  }
}

function appendRunEvent(
  state: RunState,
  event: Omit<CanonicalRunEvent, "event_seq" | "safety"> & {
    safety?: CanonicalRunEvent["safety"];
  },
): Pick<RunState, "runEvents" | "selectedEventKey" | "nextEventSeq"> {
  return appendRunEvents(state, [event]);
}

function appendRunEvents(
  state: RunState,
  events: Array<
    Omit<CanonicalRunEvent, "event_seq" | "safety"> & {
      safety?: CanonicalRunEvent["safety"];
    }
  >,
): Pick<RunState, "runEvents" | "selectedEventKey" | "nextEventSeq"> {
  let nextEventSeq = state.nextEventSeq;
  const appended = events.map((event) => ({
    ...event,
    event_seq: nextEventSeq++,
    safety: event.safety ?? createEmptyEventSafety(),
  })) as CanonicalRunEvent[];
  const runEvents = [...state.runEvents, ...appended].sort(compareRunEvents);
  const selectedEvent = runEvents[runEvents.length - 1] ?? null;

  return {
    runEvents,
    selectedEventKey: selectedEvent ? createRunEventKey(selectedEvent) : null,
    nextEventSeq,
  };
}

function createCanonicalToolEvent(
  event: ToolCallEvent,
): Omit<CanonicalRunEvent, "event_seq" | "safety"> {
  switch (event.status) {
    case "started":
      return {
        run_id: event.runId,
        event_type: "tool_call_started",
        ts: new Date(event.startedAt ?? Date.now()).toISOString(),
        tool_name: event.toolName,
        tool_call_id: event.toolCallId,
        tool_input:
          event.inputPreview === undefined
            ? {
                preview: "Tool input preview unavailable.",
              }
            : {
                preview: event.inputPreview,
              },
      };
    case "completed":
      return {
        run_id: event.runId,
        event_type: "tool_call_succeeded",
        ts: new Date(event.endedAt ?? Date.now()).toISOString(),
        tool_name: event.toolName,
        tool_call_id: event.toolCallId,
        tool_output:
          event.outputPreview === undefined
            ? {
                preview: "Tool output preview unavailable.",
              }
            : {
                preview: event.outputPreview,
              },
      };
    case "failed":
      return {
        run_id: event.runId,
        event_type: "tool_call_failed",
        ts: new Date(event.endedAt ?? Date.now()).toISOString(),
        tool_name: event.toolName,
        tool_call_id: event.toolCallId,
        error_output: {
          message: event.error ?? "Tool call failed.",
        },
      };
  }
}

function createResearchProgressEvent(
  runId: string,
  eventType:
    | "research_planning_started"
    | "research_sources_expanded"
    | "research_synthesis_started",
  timestamp: string,
  progress: CanonicalRunProgress,
  payload?: CanonicalRunEvent["tool_input"] | CanonicalRunEvent["tool_output"],
): Omit<CanonicalRunEvent, "event_seq" | "safety"> {
  if (eventType === "research_planning_started") {
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

function compareRunEvents(left: CanonicalRunEvent, right: CanonicalRunEvent): number {
  if (left.run_id !== right.run_id) {
    return left.run_id.localeCompare(right.run_id);
  }

  return left.event_seq - right.event_seq;
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
    case "web_crawl":
      return "web crawl";
  }
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

function isActiveRunEvent(state: RunState, runId: string): boolean {
  return state.activeRunId !== null && state.activeRunId === runId;
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
