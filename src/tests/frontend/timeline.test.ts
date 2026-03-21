import { describe, expect, it } from "vitest";

import {
  formatDurationMs,
  toRunEventTimelineRows,
  toTimelineRows,
} from "../../frontend/client/timeline.js";
import type { ToolCallRecord } from "../../frontend/client/state.js";
import { createEmptyRunEventSafety, type CanonicalRunEvent } from "../../frontend/contracts.js";

describe("timeline helpers", () => {
  it("projects deterministic timeline rows even when records are unordered", () => {
    const rows = toTimelineRows(
      [
        createToolCall({
          toolCallId: "tool-3",
          toolName: "web_search",
          status: "completed",
          startedAt: 150,
          endedAt: 225,
          durationMs: 75,
          sortTimestamp: 150,
          updatedAt: 225,
        }),
        createToolCall({
          toolCallId: "tool-2",
          toolName: "web_crawl",
          status: "started",
          startedAt: 100,
          sortTimestamp: 100,
          updatedAt: 120,
        }),
        createToolCall({
          toolCallId: "tool-1",
          toolName: "web_search",
          status: "failed",
          startedAt: 100,
          endedAt: 160,
          durationMs: 60,
          sortTimestamp: 100,
          updatedAt: 160,
        }),
      ],
      { nowMs: 130 },
    );

    expect(rows.map((row) => row.toolCallId)).toEqual([
      "tool-2",
      "tool-1",
      "tool-3",
    ]);
    expect(rows.map((row) => row.statusLabel)).toEqual([
      "Running",
      "Failed",
      "Completed",
    ]);
  });

  it("uses provisional elapsed duration while a tool call is still running", () => {
    const [row] = toTimelineRows(
      [
        createToolCall({
          toolCallId: "tool-1",
          toolName: "web_search",
          status: "started",
          startedAt: 1_000,
          sortTimestamp: 1_000,
          updatedAt: 1_250,
        }),
      ],
      { nowMs: 1_450 },
    );

    expect(row).toMatchObject({
      toolCallId: "tool-1",
      durationMs: 450,
      durationLabel: "450 ms",
      usesBackendDuration: false,
    });
  });

  it("prefers backend duration once a tool call completes", () => {
    const [row] = toTimelineRows(
      [
        createToolCall({
          toolCallId: "tool-1",
          toolName: "web_crawl",
          status: "completed",
          startedAt: 1_000,
          endedAt: 1_900,
          durationMs: 640,
          sortTimestamp: 1_000,
          updatedAt: 1_900,
        }),
      ],
      { nowMs: 5_000 },
    );

    expect(row).toMatchObject({
      durationMs: 640,
      durationLabel: "640 ms",
      usesBackendDuration: true,
    });
  });

  it("falls back to ended minus started for terminal rows missing backend duration", () => {
    const [row] = toTimelineRows(
      [
        createToolCall({
          toolCallId: "tool-1",
          toolName: "web_crawl",
          status: "failed",
          startedAt: 2_000,
          endedAt: 3_500,
          sortTimestamp: 2_000,
          updatedAt: 3_500,
        }),
      ],
      { nowMs: 4_000 },
    );

    expect(row).toMatchObject({
      durationMs: 1_500,
      durationLabel: "1.5 s",
      usesBackendDuration: false,
    });
  });

  it("formats long durations and preserves pending state for missing timing", () => {
    expect(formatDurationMs(12_400)).toBe("12 s");
    expect(formatDurationMs(null)).toBe("Pending");
  });

  it("renders research progress rows alongside simpler canonical events", () => {
    const rows = toRunEventTimelineRows([
      createRunEvent({
        event_seq: 0,
        event_type: "run_started",
      }),
      createRunEvent({
        event_seq: 1,
        event_type: "research_planning_started",
        progress: {
          stage: "planning",
          message: "Building the research plan.",
        },
      }),
      createRunEvent({
        event_seq: 2,
        event_type: "tool_call_started",
        tool_name: "web_search",
        tool_call_id: "tool-1",
        tool_input: {
          preview: "sources",
        },
      }),
      createRunEvent({
        event_seq: 3,
        event_type: "research_synthesis_started",
        progress: {
          stage: "synthesis",
          message: "Combining evidence.",
          completed: 2,
          total: 3,
        },
      }),
    ]);

    expect(rows.map((row) => row.eventTypeLabel)).toEqual([
      "Run started",
      "Planning",
      "Tool started",
      "Synthesis",
    ]);
    expect(rows.map((row) => row.summary)).toEqual([
      null,
      "Building the research plan.",
      "web_search",
      "Combining evidence. (2/3)",
    ]);
  });
});

function createToolCall(
  overrides: Partial<ToolCallRecord> & Pick<ToolCallRecord, "toolCallId" | "toolName" | "status">,
): ToolCallRecord {
  return {
    toolCallId: overrides.toolCallId,
    toolName: overrides.toolName,
    status: overrides.status,
    startedAt: overrides.startedAt ?? null,
    endedAt: overrides.endedAt ?? null,
    durationMs: overrides.durationMs ?? null,
    inputPreview: overrides.inputPreview ?? null,
    outputPreview: overrides.outputPreview ?? null,
    error: overrides.error ?? null,
    sortTimestamp: overrides.sortTimestamp ?? 0,
    updatedAt: overrides.updatedAt ?? overrides.sortTimestamp ?? 0,
  };
}

function createRunEvent(
  overrides: Partial<CanonicalRunEvent> &
    Pick<CanonicalRunEvent, "event_seq" | "event_type">,
): CanonicalRunEvent {
  return {
    run_id: "run-123",
    ts: "2026-03-17T12:00:00.000Z",
    safety: createEmptyRunEventSafety(),
    ...overrides,
  } as CanonicalRunEvent;
}
