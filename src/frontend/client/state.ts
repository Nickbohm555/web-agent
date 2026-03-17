import type { RunStartResponse } from "./api-client.js";
import type {
  RunCompleteEvent,
  RunErrorEvent,
  RunStateEvent,
  ToolCallEvent,
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
}

export type RunAction =
  | { type: "prompt_updated"; prompt: string }
  | { type: "run_requested" }
  | { type: "run_started"; response: RunStartResponse }
  | { type: "run_failed"; message: string }
  | { type: "run_state_received"; event: RunStateEvent }
  | { type: "tool_call_received"; event: ToolCallEvent }
  | { type: "run_completed"; event: RunCompleteEvent }
  | { type: "run_error_received"; event: RunErrorEvent };

export const initialRunState: RunState = {
  phase: "idle",
  prompt: "",
  activeRunId: null,
  error: null,
  finalAnswer: null,
  completedAt: null,
  toolCalls: [],
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

      return {
        ...state,
        phase: "running",
        toolCalls: mergeToolCall(state.toolCalls, action.event),
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
      };
  }
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
