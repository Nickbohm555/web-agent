import { describe, expect, it } from "vitest";

import {
  createEmptyRunEventSafety,
  createRunEventKey,
  parseOrderedRunEventList,
  parseRunEvent,
} from "../../frontend/contracts.js";

describe("run event contracts", () => {
  it("parses a canonical run event with payload slots and safety metadata", () => {
    const event = parseRunEvent({
      run_id: "run-123",
      event_seq: 2,
      event_type: "tool_call_succeeded",
      ts: "2026-03-17T12:00:00.000Z",
      tool_name: "web_search",
      tool_call_id: "tool-1",
      tool_input: {
        query: "latest retrieval sdk release",
      },
      tool_output: {
        results: [{ title: "Release notes" }],
      },
      error_output: null,
      safety: {
        ...createEmptyRunEventSafety(),
        tool_output: {
          redaction: {
            active: true,
            paths: ["results.0.snippet"],
            reason: "secret",
          },
          truncation: {
            active: true,
            paths: ["results"],
            omitted_bytes: 128,
          },
        },
      },
    });

    expect(createRunEventKey(event)).toBe("run-123:2");
    expect(event.safety.tool_output.redaction.active).toBe(true);
    expect(event.safety.tool_output.truncation.omitted_bytes).toBe(128);
  });

  it("rejects malformed events that omit correlation fields", () => {
    expect(() =>
      parseRunEvent({
        event_seq: 0,
        event_type: "run_started",
        ts: "2026-03-17T12:00:00.000Z",
        safety: createEmptyRunEventSafety(),
      })
    ).toThrow();
  });

  it("rejects ordered event lists with non-increasing sequence metadata", () => {
    expect(() =>
      parseOrderedRunEventList([
        {
          run_id: "run-123",
          event_seq: 3,
          event_type: "tool_call_started",
          ts: "2026-03-17T12:00:00.000Z",
          tool_name: "web_crawl",
          tool_call_id: "tool-1",
          tool_input: {
            url: "https://example.com",
          },
          safety: createEmptyRunEventSafety(),
        },
        {
          run_id: "run-123",
          event_seq: 3,
          event_type: "tool_call_failed",
          ts: "2026-03-17T12:00:01.000Z",
          tool_name: "web_crawl",
          tool_call_id: "tool-1",
          error_output: {
            code: "TIMEOUT",
          },
          safety: createEmptyRunEventSafety(),
        },
      ])
    ).toThrow(/strictly increasing/);
  });
});
