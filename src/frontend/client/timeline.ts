import {
  createRunEventKey,
  type CanonicalRunEvent,
  type CanonicalRunEventPayloadSafety,
} from "../contracts.js";
import type { ToolCallRecord } from "./state.js";

export interface TimelineRow {
  toolCallId: string;
  toolName: ToolCallRecord["toolName"];
  status: ToolCallRecord["status"];
  statusLabel: string;
  durationMs: number | null;
  durationLabel: string;
  usesBackendDuration: boolean;
}

export interface TimelineProjectionOptions {
  nowMs: number;
}

export interface RunEventTimelineRow {
  eventKey: string;
  eventSeq: number;
  eventType: CanonicalRunEvent["event_type"];
  eventTypeLabel: string;
  toolName: CanonicalRunEvent["tool_name"] | null;
  timestampLabel: string;
  safetyIndicators: string[];
}

export function toTimelineRows(
  toolCalls: ToolCallRecord[],
  options: TimelineProjectionOptions,
): TimelineRow[] {
  return [...toolCalls]
    .sort(compareToolCalls)
    .map((toolCall) => {
      const durationMs = resolveDurationMs(toolCall, options.nowMs);

      return {
        toolCallId: toolCall.toolCallId,
        toolName: toolCall.toolName,
        status: toolCall.status,
        statusLabel: formatStatusLabel(toolCall.status),
        durationMs,
        durationLabel: formatDurationMs(durationMs),
        usesBackendDuration: toolCall.durationMs !== null,
      };
    });
}

export function formatDurationMs(durationMs: number | null): string {
  if (durationMs === null) {
    return "Pending";
  }

  if (durationMs < 1_000) {
    return `${Math.round(durationMs)} ms`;
  }

  const seconds = durationMs / 1_000;
  return `${seconds.toFixed(seconds >= 10 ? 0 : 1)} s`;
}

export function toRunEventTimelineRows(events: CanonicalRunEvent[]): RunEventTimelineRow[] {
  return [...events]
    .sort((left, right) => left.event_seq - right.event_seq)
    .map((event) => ({
      eventKey: createRunEventKey(event),
      eventSeq: event.event_seq,
      eventType: event.event_type,
      eventTypeLabel: formatRunEventTypeLabel(event.event_type),
      toolName: event.tool_name ?? null,
      timestampLabel: formatEventTimestamp(event.ts),
      safetyIndicators: collectSafetyIndicators(event),
    }));
}

function resolveDurationMs(toolCall: ToolCallRecord, nowMs: number): number | null {
  if (toolCall.durationMs !== null) {
    return toolCall.durationMs;
  }

  if (toolCall.status === "started" && toolCall.startedAt !== null) {
    return Math.max(0, nowMs - toolCall.startedAt);
  }

  if (toolCall.startedAt !== null && toolCall.endedAt !== null) {
    return Math.max(0, toolCall.endedAt - toolCall.startedAt);
  }

  return null;
}

function compareToolCalls(left: ToolCallRecord, right: ToolCallRecord): number {
  if (left.sortTimestamp !== right.sortTimestamp) {
    return left.sortTimestamp - right.sortTimestamp;
  }

  if (left.updatedAt !== right.updatedAt) {
    return left.updatedAt - right.updatedAt;
  }

  return left.toolCallId.localeCompare(right.toolCallId);
}

function formatStatusLabel(status: ToolCallRecord["status"]): string {
  switch (status) {
    case "started":
      return "Running";
    case "completed":
      return "Completed";
    case "failed":
      return "Failed";
  }
}

function formatRunEventTypeLabel(eventType: CanonicalRunEvent["event_type"]): string {
  switch (eventType) {
    case "run_started":
      return "Run started";
    case "tool_call_started":
      return "Tool started";
    case "tool_call_succeeded":
      return "Tool succeeded";
    case "tool_call_failed":
      return "Tool failed";
    case "final_answer_generated":
      return "Final answer";
    case "run_completed":
      return "Run completed";
    case "run_failed":
      return "Run failed";
  }
}

function formatEventTimestamp(timestamp: string): string {
  const parsed = new Date(timestamp);

  if (Number.isNaN(parsed.getTime())) {
    return "Invalid timestamp";
  }

  return parsed.toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
  });
}

function collectSafetyIndicators(event: CanonicalRunEvent): string[] {
  const indicators: string[] = [];
  appendIndicators(indicators, event.safety.tool_input, "input");
  appendIndicators(indicators, event.safety.tool_output, "output");
  appendIndicators(indicators, event.safety.error_output, "error");
  return indicators;
}

function appendIndicators(
  indicators: string[],
  safety: CanonicalRunEventPayloadSafety,
  label: "input" | "output" | "error",
) {
  if (safety.redaction.active) {
    indicators.push(`${label} redacted`);
  }

  if (safety.truncation.active) {
    indicators.push(`${label} truncated`);
  }
}
