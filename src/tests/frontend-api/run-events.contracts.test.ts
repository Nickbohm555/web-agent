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
      tool_name: "open_url",
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

  it("parses research progress events with explicit stage metadata", () => {
    const event = parseRunEvent({
      run_id: "run-123",
      event_seq: 4,
      event_type: "research_sources_expanded",
      ts: "2026-03-17T12:00:01.500Z",
      progress: {
        stage: "source_expansion",
        message: "Collecting additional sources from search.",
        completed: 2,
        total: 4,
      },
      tool_output: {
        sourceCount: 4,
      },
      safety: createEmptyRunEventSafety(),
    });

    expect(event.progress).toEqual({
      stage: "source_expansion",
      message: "Collecting additional sources from search.",
      completed: 2,
      total: 4,
    });
    expect(event.tool_output).toEqual({
      sourceCount: 4,
    });
  });

  it("parses typed search and verification progress events", () => {
    const searchEvent = parseRunEvent({
      run_id: "run-123",
      event_seq: 5,
      event_type: "research_search_started",
      ts: "2026-03-17T12:00:01.750Z",
      progress: {
        stage: "search",
        message: "Searching and reranking sources for \"sdk retry budget\".",
      },
      tool_input: {
        query: "sdk retry budget",
      },
      safety: createEmptyRunEventSafety(),
    });
    const verificationEvent = parseRunEvent({
      run_id: "run-123",
      event_seq: 6,
      event_type: "research_verification_started",
      ts: "2026-03-17T12:00:01.900Z",
      progress: {
        stage: "verification",
        message: "Checking evidence for \"retry budget\" within the opened page.",
      },
      tool_output: {
        sourceCount: 2,
      },
      safety: createEmptyRunEventSafety(),
    });

    expect(searchEvent.progress?.stage).toBe("search");
    expect(searchEvent.tool_input).toEqual({
      query: "sdk retry budget",
    });
    expect(verificationEvent.progress?.stage).toBe("verification");
    expect(verificationEvent.tool_output).toEqual({
      sourceCount: 2,
    });
  });

  it("parses typed retrieval action events with explicit search/open/find metadata", () => {
    const event = parseRunEvent({
      run_id: "run-123",
      event_seq: 5,
      event_type: "retrieval_action_succeeded",
      ts: "2026-03-17T12:00:02.000Z",
      retrieval_action: {
        action_id: "action-1",
        action_type: "find_in_page",
        url: "https://example.com/release-notes",
        pattern: "retry budget",
        match_count: 2,
      },
      tool_output: {
        preview: "Found retry budget references",
        match_count: 2,
      },
      safety: createEmptyRunEventSafety(),
    });

    expect(event.retrieval_action).toEqual({
      action_id: "action-1",
      action_type: "find_in_page",
      url: "https://example.com/release-notes",
      pattern: "retry budget",
      match_count: 2,
    });
    expect(event.tool_output).toEqual({
      preview: "Found retry budget references",
      match_count: 2,
    });
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

  it("rejects research progress events with mismatched stage metadata", () => {
    expect(() =>
      parseRunEvent({
        run_id: "run-123",
        event_seq: 6,
        event_type: "research_synthesis_started",
        ts: "2026-03-17T12:00:03.000Z",
        progress: {
          stage: "planning",
          message: "Wrong stage",
        },
        safety: createEmptyRunEventSafety(),
      })
    ).toThrow(/synthesis stage/i);
  });

  it("rejects search progress events with a non-search stage", () => {
    expect(() =>
      parseRunEvent({
        run_id: "run-123",
        event_seq: 7,
        event_type: "research_search_started",
        ts: "2026-03-17T12:00:03.000Z",
        progress: {
          stage: "crawl",
          message: "Wrong stage",
        },
        safety: createEmptyRunEventSafety(),
      })
    ).toThrow(/search stage/i);
  });

  it("rejects malformed retrieval actions that omit required typed fields", () => {
    expect(() =>
      parseRunEvent({
        run_id: "run-123",
        event_seq: 7,
        event_type: "retrieval_action_started",
        ts: "2026-03-17T12:00:03.000Z",
        retrieval_action: {
          action_id: "action-2",
          action_type: "search",
        },
        safety: createEmptyRunEventSafety(),
      })
    ).toThrow(/query/i);
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
        tool_name: "open_url",
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
          tool_name: "open_url",
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
          tool_name: "open_url",
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
