import { describe, expect, it } from "vitest";

import {
  initialRunState,
  reduceRunState,
  type RunAction,
} from "../../frontend/client/state.js";

describe("run state reducer", () => {
  it("tracks the selected run mode and preserves it across run start", () => {
    const state = applyActions([
      { type: "mode_updated", mode: "agentic" },
      { type: "prompt_updated", prompt: "Build a market map" },
      { type: "run_requested" },
      {
        type: "run_started",
        response: {
          runId: "run-123",
          status: "queued",
        },
      },
    ]);

    expect(state.selectedMode).toBe("agentic");
    expect(state.runEvents[0]).toMatchObject({
      event_type: "run_started",
      tool_input: {
        prompt: "Build a market map",
        mode: "agentic",
      },
    });
    expect(state.runEvents[1]).toMatchObject({
      event_type: "research_planning_started",
      progress: {
        stage: "planning",
        message:
          "Building an exploratory research plan and selecting retrieval paths.",
      },
      tool_input: {
        prompt: "Build a market map",
        mode: "agentic",
      },
    });
  });

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
          toolName: "open_url",
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
          sources: [],
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
          toolName: "open_url",
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
          toolName: "open_url",
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

  it("adds research progress milestones around live run events", () => {
    const state = applyActions([
      { type: "prompt_updated", prompt: "Investigate provider reliability" },
      { type: "mode_updated", mode: "quick" },
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
          inputPreview: "provider reliability",
        },
      },
      {
        type: "run_completed",
        event: {
          runId: "run-123",
          finalAnswer: "Provider A had fewer outages.",
          structuredAnswer: {
            text: "Provider A had fewer outages.",
            basis: [],
            citations: [
              {
                source_id: "provider-status",
                title: "Provider status report",
                url: "https://example.com/status",
                start_index: 0,
                end_index: 10,
              },
            ],
          },
          sources: [
            {
              source_id: "provider-status",
              title: "Provider status report",
              url: "https://example.com/status",
              snippet: "Weekly outage summary.",
            },
          ],
          completedAt: 300,
          durationMs: 200,
        },
      },
    ]);

    expect(state.runEvents.map((event) => event.event_type)).toEqual([
      "run_started",
      "research_planning_started",
      "research_search_started",
      "tool_call_started",
      "research_verification_started",
      "research_synthesis_started",
      "final_answer_generated",
      "run_completed",
    ]);
    expect(state.runEvents[1]).toMatchObject({
      event_type: "research_planning_started",
      progress: {
        stage: "planning",
        message: "Starting a fast search pass for a concise answer.",
      },
      tool_input: {
        prompt: "Investigate provider reliability",
        mode: "quick",
      },
    });
    expect(state.runEvents[2]).toMatchObject({
      event_type: "research_search_started",
      progress: {
        stage: "search",
      },
    });
    expect(state.runEvents[4]).toMatchObject({
      event_type: "research_verification_started",
      progress: {
        stage: "verification",
        completed: 0,
        total: 1,
      },
    });
    expect(state.runEvents[5]).toMatchObject({
      event_type: "research_synthesis_started",
      progress: {
        stage: "synthesis",
        completed: 0,
        total: 1,
      },
    });
    expect(state.runEvents[6]).toMatchObject({
      event_type: "final_answer_generated",
      final_answer: "Provider A had fewer outages.",
    });
    expect(state.runEvents[6]?.tool_output).toEqual({
      answer: {
        text: "Provider A had fewer outages.",
        basis: [],
        citations: [
          {
            source_id: "provider-status",
            title: "Provider status report",
            url: "https://example.com/status",
            start_index: 0,
            end_index: 10,
          },
        ],
      },
      sources: [
        {
          source_id: "provider-status",
          title: "Provider status report",
          url: "https://example.com/status",
          snippet: "Weekly outage summary.",
        },
      ],
    });
  });

  it("records retrieval actions as canonical search, crawl, and verification milestones", () => {
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
        type: "retrieval_action_received",
        event: {
          runId: "run-123",
          actionId: "action-search",
          actionType: "search",
          status: "started",
          query: "provider reliability benchmark",
          startedAt: 100,
        },
      },
      {
        type: "retrieval_action_received",
        event: {
          runId: "run-123",
          actionId: "action-open",
          actionType: "open_page",
          status: "started",
          url: "https://example.com/benchmark",
          startedAt: 120,
        },
      },
      {
        type: "retrieval_action_received",
        event: {
          runId: "run-123",
          actionId: "action-find",
          actionType: "find_in_page",
          status: "started",
          url: "https://example.com/benchmark",
          pattern: "outage rate",
          startedAt: 140,
        },
      },
    ]);

    expect(state.runEvents.map((event) => event.event_type)).toEqual([
      "run_started",
      "research_planning_started",
      "research_search_started",
      "retrieval_action_started",
      "research_crawl_started",
      "retrieval_action_started",
      "research_verification_started",
      "retrieval_action_started",
    ]);
    expect(state.runEvents[2]).toMatchObject({
      progress: {
        stage: "search",
      },
      tool_input: {
        query: "provider reliability benchmark",
      },
    });
    expect(state.runEvents[4]).toMatchObject({
      progress: {
        stage: "crawl",
      },
      tool_input: {
        url: "https://example.com/benchmark",
      },
    });
    expect(state.runEvents[6]).toMatchObject({
      progress: {
        stage: "verification",
      },
      tool_output: {
        url: "https://example.com/benchmark",
        pattern: "outage rate",
      },
    });
  });
});

function applyActions(actions: RunAction[]) {
  return actions.reduce(reduceRunState, initialRunState);
}
