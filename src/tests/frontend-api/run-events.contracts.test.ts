import { describe, expect, it } from "vitest";

import {
  createEmptyRunEventSafety,
  createRunEventKey,
  parseOrderedRunEventList,
  parseRunEvent,
} from "../../frontend/contracts.js";

describe("run event contracts", () => {
  it("parses a canonical success event with visible input/output payloads and safety metadata", () => {
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
    expect(event.tool_input).toEqual({
      query: "latest retrieval sdk release",
    });
    expect(event.tool_output).toEqual({
      results: [{ title: "Release notes" }],
    });
    expect(event.safety.tool_output.redaction.active).toBe(true);
    expect(event.safety.tool_output.truncation.omitted_bytes).toBe(128);
  });

  it("parses a canonical failure event with visible input/error payloads", () => {
    const event = parseRunEvent({
      run_id: "run-123",
      event_seq: 3,
      event_type: "tool_call_failed",
      ts: "2026-03-17T12:00:01.000Z",
      tool_name: "web_crawl",
      tool_call_id: "tool-2",
      tool_input: {
        url: "https://example.com/private",
        apiKey: "[Redacted]",
      },
      error_output: {
        code: "POLICY_DENIED",
        token: "[Redacted]",
      },
      safety: {
        ...createEmptyRunEventSafety(),
        tool_input: {
          redaction: {
            active: true,
            paths: ["apiKey"],
            reason: "secret",
          },
          truncation: {
            active: false,
            paths: [],
          },
        },
        error_output: {
          redaction: {
            active: true,
            paths: ["token"],
            reason: "secret",
          },
          truncation: {
            active: false,
            paths: [],
          },
        },
      },
    });

    expect(event.tool_input).toEqual({
      url: "https://example.com/private",
      apiKey: "[Redacted]",
    });
    expect(event.error_output).toEqual({
      code: "POLICY_DENIED",
      token: "[Redacted]",
    });
    expect(event.safety.error_output.redaction.paths).toEqual(["token"]);
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

  it("rejects events that leak raw secrets into payloads", () => {
    expect(() =>
      parseRunEvent({
        run_id: "run-123",
        event_seq: 4,
        event_type: "tool_call_started",
        ts: "2026-03-17T12:00:02.000Z",
        tool_name: "web_search",
        tool_call_id: "tool-3",
        tool_input: {
          headers: {
            authorization: "Bearer super-secret-token",
          },
        },
        safety: createEmptyRunEventSafety(),
      })
    ).toThrow(/must be redacted/i);
  });

  it("rejects redacted payload markers that omit matching safety paths", () => {
    expect(() =>
      parseRunEvent({
        run_id: "run-123",
        event_seq: 5,
        event_type: "tool_call_failed",
        ts: "2026-03-17T12:00:03.000Z",
        tool_name: "web_crawl",
        tool_call_id: "tool-4",
        error_output: {
          token: "[Redacted]",
        },
        safety: {
          ...createEmptyRunEventSafety(),
          error_output: {
            redaction: {
              active: true,
              paths: [],
              reason: "secret",
            },
            truncation: {
              active: false,
              paths: [],
            },
          },
        },
      })
    ).toThrow(/matching safety metadata|at least one path/i);
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
