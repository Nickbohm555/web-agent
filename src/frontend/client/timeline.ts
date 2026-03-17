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
