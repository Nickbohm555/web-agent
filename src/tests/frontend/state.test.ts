import { describe, expect, it } from "vitest";

import {
  initialRunState,
  reduceRunState,
  type RunAction,
} from "../../frontend/client/state.js";

describe("run state reducer", () => {
  it("merges out-of-order tool events by toolCallId without duplicating records", () => {
    const state = applyActions([
      { type: "prompt_updated", prompt: "Find sources" },
      { type: "run_requested" },
      {
        type: "run_started",
        response: {
          runId: "run-123",
          status: "queued",
        },
      },
      {
        type: "tool_call_received",
        event: {
          runId: "run-123",
          toolCallId: "tool-1",
          toolName: "web_search",
          status: "completed",
          endedAt: 300,
          durationMs: 200,
          outputPreview: "Two results",
        },
      },
      {
        type: "tool_call_received",
        event: {
          runId: "run-123",
          toolCallId: "tool-1",
          toolName: "web_search",
          status: "started",
          startedAt: 100,
          inputPreview: "Find sources",
        },
      },
      {
        type: "tool_call_received",
        event: {
          runId: "run-123",
          toolCallId: "tool-1",
          toolName: "web_search",
          status: "completed",
          endedAt: 300,
          durationMs: 200,
          outputPreview: "Two results",
        },
      },
    ]);

    expect(state.phase).toBe("running");
    expect(state.toolCalls).toHaveLength(1);
    expect(state.toolCalls[0]).toMatchObject({
      toolCallId: "tool-1",
      toolName: "web_search",
      status: "completed",
      startedAt: 100,
      endedAt: 300,
      durationMs: 200,
      inputPreview: "Find sources",
      outputPreview: "Two results",
      sortTimestamp: 100,
      updatedAt: 300,
    });
  });

  it("keeps tool call ordering deterministic when events arrive out of order", () => {
    const state = applyActions([
      { type: "run_requested" },
      {
        type: "run_started",
        response: {
          runId: "run-123",
          status: "running",
        },
      },
      {
        type: "tool_call_received",
        event: {
          runId: "run-123",
          toolCallId: "tool-2",
          toolName: "web_crawl",
          status: "started",
          startedAt: 200,
        },
      },
      {
        type: "tool_call_received",
        event: {
          runId: "run-123",
          toolCallId: "tool-1",
          toolName: "web_search",
          status: "completed",
          startedAt: 100,
          endedAt: 150,
          durationMs: 50,
        },
      },
    ]);

    expect(state.toolCalls.map((toolCall) => toolCall.toolCallId)).toEqual([
      "tool-1",
      "tool-2",
    ]);
  });

  it("rejects stale state regressions after terminal completion", () => {
    const state = applyActions([
      { type: "run_requested" },
      {
        type: "run_started",
        response: {
          runId: "run-123",
          status: "queued",
        },
      },
      {
        type: "tool_call_received",
        event: {
          runId: "run-123",
          toolCallId: "tool-1",
          toolName: "web_search",
          status: "started",
          startedAt: 100,
        },
      },
      {
        type: "run_completed",
        event: {
          runId: "run-123",
          finalAnswer: "Answer",
          completedAt: 400,
          durationMs: 300,
        },
      },
      {
        type: "run_state_received",
        event: {
          runId: "run-123",
          state: "running",
          ts: 450,
        },
      },
      {
        type: "tool_call_received",
        event: {
          runId: "run-123",
          toolCallId: "tool-2",
          toolName: "web_crawl",
          status: "started",
          startedAt: 500,
        },
      },
      {
        type: "run_error_received",
        event: {
          runId: "run-123",
          message: "Late failure",
          failedAt: 550,
        },
      },
    ]);

    expect(state.phase).toBe("completed");
    expect(state.finalAnswer).toBe("Answer");
    expect(state.completedAt).toBe(400);
    expect(state.error).toBeNull();
    expect(state.toolCalls).toHaveLength(1);
    expect(state.toolCalls[0]?.toolCallId).toBe("tool-1");
  });

  it("ignores stale events from a different run and preserves active run state", () => {
    const state = applyActions([
      { type: "run_requested" },
      {
        type: "run_started",
        response: {
          runId: "run-123",
          status: "queued",
        },
      },
      {
        type: "run_state_received",
        event: {
          runId: "run-456",
          state: "failed",
          ts: 10,
        },
      },
      {
        type: "tool_call_received",
        event: {
          runId: "run-456",
          toolCallId: "tool-9",
          toolName: "web_crawl",
          status: "failed",
          endedAt: 20,
          durationMs: 10,
          error: "Wrong run",
        },
      },
    ]);

    expect(state.phase).toBe("running");
    expect(state.activeRunId).toBe("run-123");
    expect(state.toolCalls).toEqual([]);
  });
});

function applyActions(actions: RunAction[]) {
  return actions.reduce(reduceRunState, initialRunState);
}
