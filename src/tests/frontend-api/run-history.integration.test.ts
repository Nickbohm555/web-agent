import type { AddressInfo } from "node:net";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  parseRunHistoryListResponse,
  parseRunHistoryNotFoundError,
  parseRunHistoryRunSnapshot,
  RunStartResponseSchema,
  type RunStreamEvent,
} from "../../frontend/contracts.js";
import {
  resolveRunAnswer,
  segmentStructuredAnswer,
} from "../../frontend/client/answer-rendering.js";
import { createRunHistoryStore } from "../../frontend/run-history/store.js";
import type { RunEventStreamFactory } from "../../frontend/routes/runs.js";

describe("run history API", () => {
  beforeEach(() => {
    vi.resetModules();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns empty history list responses and a typed not-found detail response", async () => {
    const harness = await createHarness();

    try {
      const response = await harness.getJson("/api/runs/history");

      expect(response.status).toBe(200);
      expect(parseRunHistoryListResponse(response.json)).toEqual({
        runs: [],
      });

      const notFoundResponse = await harness.getJson("/api/runs/run-missing/history");

      expect(notFoundResponse.status).toBe(404);
      expect(parseRunHistoryNotFoundError(notFoundResponse.json)).toEqual({
        error: {
          code: "RUN_HISTORY_NOT_FOUND",
          message: "Run history for 'run-missing' was not found.",
        },
      });
    } finally {
      await harness.close();
    }
  });

  it("stores one cohesive run-view snapshot with final answer and ordered tool trace", async () => {
    const harness = await createHarness({
      runEventStream: createStream([
        {
          event: "tool_call",
          data: {
            runId: "__RUN_ID__",
            toolCallId: "tool-1",
            toolName: "web_search",
            status: "started",
            startedAt: Date.parse("2026-03-17T00:00:01.000Z"),
            inputPreview: "{\"query\":\"agents\"}",
          },
        },
        {
          event: "tool_call",
          data: {
            runId: "__RUN_ID__",
            toolCallId: "tool-1",
            toolName: "web_search",
            status: "completed",
            startedAt: Date.parse("2026-03-17T00:00:01.000Z"),
            endedAt: Date.parse("2026-03-17T00:00:02.000Z"),
            durationMs: 1000,
            outputPreview: "{\"top\":\"result\"}",
          },
        },
        {
          event: "run_complete",
          data: {
            runId: "__RUN_ID__",
            finalAnswer: "Answer with citations.",
            sources: [],
            completedAt: Date.parse("2026-03-17T00:00:03.000Z"),
            durationMs: 3000,
          },
        },
      ]),
    });

    try {
      const startResponse = await harness.postJson("/api/runs", {
        prompt: "Find sources",
        mode: "quick",
      });
      expect(startResponse.status).toBe(201);

      const runId = parseRunId(startResponse.json);
      const streamText = await harness.getText(`/api/runs/${runId}/events`);
      expect(streamText.status).toBe(200);
      expect(streamText.body).toContain("event: tool_call");
      expect(streamText.body).toContain("event: run_complete");

      const listResponse = await harness.getJson("/api/runs/history");
      expect(listResponse.status).toBe(200);
      const listPayload = parseRunHistoryListResponse(listResponse.json);
      expect(listPayload.runs).toHaveLength(1);
      expect(listPayload.runs[0]).toMatchObject({
        runId,
        finalAnswer: "Answer with citations.",
        eventCount: 10,
        latestEventSeq: 9,
      });

      const detailResponse = await harness.getJson(`/api/runs/${runId}/history`);
      expect(detailResponse.status).toBe(200);
      const detailPayload = parseRunHistoryRunSnapshot(detailResponse.json);
      expect(detailPayload.runId).toBe(runId);
      expect(detailPayload.finalAnswer).toBe("Answer with citations.");
      expect(detailPayload.events.map((event) => event.event_seq)).toEqual([
        0, 1, 2, 3, 4, 5, 6, 7, 8, 9,
      ]);
      expect(detailPayload.events.map((event) => event.event_type)).toEqual([
        "run_started",
        "research_planning_started",
        "research_search_started",
        "tool_call_started",
        "research_sources_expanded",
        "tool_call_succeeded",
        "research_verification_started",
        "research_synthesis_started",
        "final_answer_generated",
        "run_completed",
      ]);
      expect(detailPayload.events[0]?.tool_input).toEqual({
        prompt: "Find sources",
        mode: "quick",
      });
      expect(detailPayload.events.at(-1)?.final_answer).toBe(
        "Answer with citations.",
      );
      expect(detailPayload.retention.eventsDropped).toBe(0);
      expect(detailPayload.retention.payloadTruncations).toEqual([]);
    } finally {
      await harness.close();
    }
  });

  it("surfaces bounded history metadata for dropped events and truncated payloads", async () => {
    const harness = await createHarness({
      store: createRunHistoryStore({
        maxRuns: 5,
        maxEventsPerRun: 3,
        maxPayloadBytes: 80,
      }),
      runEventStream: createStream([
        {
          event: "tool_call",
          data: {
            runId: "__RUN_ID__",
            toolCallId: "tool-1",
            toolName: "web_search",
            status: "started",
            startedAt: Date.parse("2026-03-17T00:00:01.000Z"),
            inputPreview: "x".repeat(200),
          },
        },
        {
          event: "tool_call",
          data: {
            runId: "__RUN_ID__",
            toolCallId: "tool-1",
            toolName: "web_search",
            status: "completed",
            startedAt: Date.parse("2026-03-17T00:00:01.000Z"),
            endedAt: Date.parse("2026-03-17T00:00:02.000Z"),
            durationMs: 1000,
            outputPreview: "y".repeat(220),
          },
        },
        {
          event: "tool_call",
          data: {
            runId: "__RUN_ID__",
            toolCallId: "tool-2",
            toolName: "open_url",
            status: "failed",
            startedAt: Date.parse("2026-03-17T00:00:03.000Z"),
            endedAt: Date.parse("2026-03-17T00:00:04.000Z"),
            error: "blocked",
            inputPreview: "z".repeat(180),
          },
        },
        {
          event: "run_complete",
          data: {
            runId: "__RUN_ID__",
            finalAnswer: "A very long final answer ".repeat(20),
            sources: [],
            completedAt: Date.parse("2026-03-17T00:00:05.000Z"),
            durationMs: 5000,
          },
        },
      ]),
    });

    try {
      const startResponse = await harness.postJson("/api/runs", {
        prompt: "Bounded run",
        mode: "quick",
      });
      const runId = parseRunId(startResponse.json);

      await harness.getText(`/api/runs/${runId}/events`);

      const detailResponse = await harness.getJson(`/api/runs/${runId}/history`);
      const detailPayload = parseRunHistoryRunSnapshot(detailResponse.json);

      expect(detailPayload.events.map((event) => event.event_seq)).toEqual([
        8, 9, 10,
      ]);
      expect(detailPayload.retention.eventsDropped).toBe(8);
      expect(detailPayload.retention.payloadTruncations.length).toBeGreaterThan(0);
      expect(detailPayload.retention.payloadTruncations.some((entry) => {
        return entry.fields.includes("tool_input") || entry.fields.includes("tool_output");
      })).toBe(true);
      expect(detailPayload.finalAnswer).toContain("[Truncated run history answer]");
    } finally {
      await harness.close();
    }
  });

  it("preserves citation-aware completion payloads safely after history truncation", async () => {
    const harness = await createHarness({
      store: createRunHistoryStore({
        maxRuns: 5,
        maxEventsPerRun: 10,
        maxPayloadBytes: 700,
      }),
      runEventStream: createStream([
        {
          event: "run_complete",
          data: {
            runId: "__RUN_ID__",
            finalAnswer:
              "Alpha remains ahead of Beta in the latest benchmark results while Gamma trails. ".repeat(
                4,
              ),
            structuredAnswer: {
              text:
                "Alpha remains ahead of Beta in the latest benchmark results while Gamma trails. ".repeat(
                  4,
                ),
              basis: [],
              citations: [
                {
                  source_id: "alpha-report",
                  title: "Alpha report",
                  url: "https://example.com/alpha",
                  start_index: 0,
                  end_index: 13,
                },
                {
                  source_id: "beta-report",
                  title: "Beta report",
                  url: "https://example.com/beta",
                  start_index: 31,
                  end_index: 35,
                },
                {
                  source_id: "gamma-report",
                  title: "Gamma report",
                  url: "https://example.com/gamma",
                  start_index: 72,
                  end_index: 77,
                },
              ],
            },
            sources: [
              {
                source_id: "alpha-report",
                title: "Alpha report",
                url: "https://example.com/alpha",
                snippet: "Alpha evidence ".repeat(20),
              },
              {
                source_id: "beta-report",
                title: "Beta report",
                url: "https://example.com/beta",
                snippet: "Beta evidence ".repeat(20),
              },
              {
                source_id: "gamma-report",
                title: "Gamma report",
                url: "https://example.com/gamma",
                snippet: "Gamma evidence ".repeat(20),
              },
            ],
            completedAt: Date.parse("2026-03-17T00:00:03.000Z"),
            durationMs: 3000,
          },
        },
      ]),
    });

    try {
      const startResponse = await harness.postJson("/api/runs", {
        prompt: "Store large structured answer",
        mode: "quick",
      });
      expect(startResponse.status).toBe(201);

      const runId = parseRunId(startResponse.json);
      await harness.getText(`/api/runs/${runId}/events`);

      const detailResponse = await harness.getJson(`/api/runs/${runId}/history`);
      expect(detailResponse.status).toBe(200);
      const snapshot = parseRunHistoryRunSnapshot(detailResponse.json);
      const resolved = resolveRunAnswer(snapshot.events, snapshot.finalAnswer);

      expect(snapshot.retention.payloadTruncations.some((entry) => {
        return entry.fields.includes("tool_output");
      })).toBe(true);
      expect(resolved.structuredAnswer).not.toBeNull();

      const structuredAnswer = resolved.structuredAnswer;
      if (structuredAnswer === null) {
        throw new Error("Expected structured answer to be preserved.");
      }

      const sourceIds = new Set(resolved.sources.map((source) => source.source_id));
      expect(structuredAnswer.text).toContain("[Truncated run history answer]");
      expect(structuredAnswer.citations.every((citation) => {
        return citation.end_index <= structuredAnswer.text.length;
      })).toBe(true);
      expect(structuredAnswer.citations.every((citation) => {
        return sourceIds.has(citation.source_id);
      })).toBe(true);

      const segments = segmentStructuredAnswer(structuredAnswer, resolved.sources);
      expect(segments.map((segment) => segment.text).join("")).toBe(
        structuredAnswer.text,
      );
    } finally {
      await harness.close();
    }
  });

  it("rejects non-quick launcher modes before any run stream is consumed", async () => {
    let allowCompletion = () => {};
    const completionGate = new Promise<void>((resolve) => {
      allowCompletion = resolve;
    });
    const harness = await createHarness({
      runEventStream: async function* (context) {
        yield {
          event: "tool_call",
          data: {
            runId: context.runId,
            toolCallId: "tool-1",
            toolName: "web_search",
            status: "started",
            startedAt: Date.parse("2026-03-17T00:00:01.000Z"),
            inputPreview: "{\"query\":\"deep research\"}",
          },
        };
        await new Promise((resolve) => setTimeout(resolve, 5));
        yield {
          event: "tool_call",
          data: {
            runId: context.runId,
            toolCallId: "tool-1",
            toolName: "web_search",
            status: "completed",
            startedAt: Date.parse("2026-03-17T00:00:01.000Z"),
            endedAt: Date.parse("2026-03-17T00:00:02.000Z"),
            durationMs: 1000,
            outputPreview: "{\"top\":\"result\"}",
          },
        };
        await new Promise((resolve) => setTimeout(resolve, 5));
        await completionGate;
        yield {
          event: "run_complete",
          data: {
            runId: context.runId,
            finalAnswer: "Long-running answer.",
            sources: [],
            completedAt: Date.parse("2026-03-17T00:00:03.000Z"),
            durationMs: 3000,
          },
        };
      },
    });

    try {
      const startResponse = await harness.postJson("/api/runs", {
        prompt: "Investigate the market",
        mode: "agentic",
      });
      expect(startResponse.status).toBe(400);
      expect(startResponse.json).toMatchObject({
        ok: false,
        operation: "run_start",
        error: {
          code: "INVALID_REQUEST",
          message: "Use the agentic chat route for conversational workflows.",
        },
      });
    } finally {
      await harness.close();
    }
  });

  it("rejects removed deep-research starts on the launcher route", async () => {
    const harness = await createHarness({
      runEventStream: async function* () {
        await new Promise(() => {});
      },
    });

    try {
      const rejectedResponse = await harness.postJson("/api/runs", {
        prompt: "Concurrency check",
        mode: "deep_research",
      });

      expect(rejectedResponse.status).toBe(400);
      expect(rejectedResponse.json).toMatchObject({
        ok: false,
        operation: "run_start",
        error: {
          code: "VALIDATION_ERROR",
        },
      });
    } finally {
      await harness.close();
    }
  });

  it.each([
    ["quick", false],
  ] as const)(
    "preserves a coherent happy-path run lifecycle for %s mode",
    async (mode, startsInBackground) => {
      const runExecutor = vi.fn(async ({ prompt, mode: selectedMode }) => ({
        status: "completed" as const,
        finalAnswer: `Completed ${selectedMode} run for ${prompt}.`,
        sources: [
          {
            source_id: `${selectedMode}-source`,
            title: `${selectedMode} source`,
            url: `https://example.com/${selectedMode}`,
            snippet: `Evidence for ${selectedMode}.`,
          },
        ],
        durationMs: 42,
        completedAt: Date.parse("2026-03-17T00:00:03.000Z"),
      }));
      const harness = await createHarness({ runExecutor });

      try {
        const startResponse = await harness.postJson("/api/runs", {
          prompt: `Verify ${mode} lifecycle`,
          mode,
        });
        expect(startResponse.status).toBe(201);

        const runId = parseRunId(startResponse.json);
        expect(runExecutor).toHaveBeenCalledTimes(startsInBackground ? 1 : 0);

        const streamText = await harness.getText(`/api/runs/${runId}/events`);
        expect(streamText.status).toBe(200);
        expect(parseSseFrames(streamText.body).map((frame) => frame.event)).toEqual([
          "run_state",
          "run_complete",
        ]);

        expect(runExecutor).toHaveBeenCalledTimes(1);
        expect(runExecutor).toHaveBeenCalledWith({
          runId,
          prompt: `Verify ${mode} lifecycle`,
          mode,
          signal: expect.any(AbortSignal),
        });

        const detailResponse = await harness.getJson(`/api/runs/${runId}/history`);
        expect(detailResponse.status).toBe(200);
        const snapshot = parseRunHistoryRunSnapshot(detailResponse.json);
        expect(snapshot.finalAnswer).toBe(`Completed ${mode} run for Verify ${mode} lifecycle.`);
        expect(snapshot.events.map((event) => event.event_type)).toEqual([
          "run_started",
          "research_planning_started",
          "research_verification_started",
          "research_synthesis_started",
          "final_answer_generated",
          "run_completed",
        ]);
        expect(snapshot.events[0]?.tool_input).toEqual({
          prompt: `Verify ${mode} lifecycle`,
          mode,
        });
      } finally {
        await harness.close();
      }
    },
  );

  it.each([
    ["quick", false],
  ] as const)(
    "preserves a coherent failure-path run lifecycle for %s mode",
    async (mode, startsInBackground) => {
      const runExecutor = vi.fn(async () => ({
        status: "failed" as const,
        message: `${mode} execution failed`,
        code: `${mode.toUpperCase()}_FAILED`,
        failedAt: Date.parse("2026-03-17T00:00:03.000Z"),
      }));
      const harness = await createHarness({ runExecutor });

      try {
        const startResponse = await harness.postJson("/api/runs", {
          prompt: `Break ${mode} lifecycle`,
          mode,
        });
        expect(startResponse.status).toBe(201);

        const runId = parseRunId(startResponse.json);
        expect(runExecutor).toHaveBeenCalledTimes(startsInBackground ? 1 : 0);

        const streamText = await harness.getText(`/api/runs/${runId}/events`);
        expect(streamText.status).toBe(200);
        expect(parseSseFrames(streamText.body).map((frame) => frame.event)).toEqual([
          "run_state",
          "run_error",
        ]);

        expect(runExecutor).toHaveBeenCalledTimes(1);

        const detailResponse = await harness.getJson(`/api/runs/${runId}/history`);
        expect(detailResponse.status).toBe(200);
        const snapshot = parseRunHistoryRunSnapshot(detailResponse.json);
        expect(snapshot.finalAnswer).toBeNull();
        expect(snapshot.events.map((event) => event.event_type)).toEqual([
          "run_started",
          "research_planning_started",
          "run_failed",
        ]);
        expect(snapshot.events[2]).toMatchObject({
          event_type: "run_failed",
          error_output: {
            message: `${mode} execution failed`,
            code: `${mode.toUpperCase()}_FAILED`,
          },
        });
      } finally {
        await harness.close();
      }
    },
  );
});

function parseRunId(input: unknown): string {
  if (
    typeof input !== "object" ||
    input === null ||
    typeof (input as { runId?: unknown }).runId !== "string"
  ) {
    throw new Error("Expected run start response with runId.");
  }

  return (input as { runId: string }).runId;
}

function createStream(events: RunStreamEvent[]): RunEventStreamFactory {
  return async function* stream(context) {
    for (const event of events) {
      yield replaceRunId(event, context.runId);
    }
  };
}

function replaceRunId(event: RunStreamEvent, runId: string): RunStreamEvent {
  return {
    ...event,
    data: {
      ...event.data,
      runId,
    },
  } as RunStreamEvent;
}

async function createHarness(options: {
  store?: ReturnType<typeof createRunHistoryStore>;
  runEventStream?: RunEventStreamFactory;
  runExecutor?: (
    context: {
      runId: string;
      prompt: string;
      mode: "quick" | "agentic";
      signal: AbortSignal;
    },
  ) => Promise<
    | {
      status: "completed";
      finalAnswer: string;
      sources: Array<{ source_id: string; title: string; url: string; snippet: string }>;
      durationMs: number;
      completedAt: number;
    }
    | {
      status: "failed";
      message: string;
      code: string;
      failedAt: number;
    }
  >;
} = {}) {
  const { createFrontendServerApp } = await import("../../frontend/server.js");
  const app = createFrontendServerApp();
  app.locals.runHistoryStore = options.store ?? createRunHistoryStore();
  if (options.runEventStream !== undefined) {
    app.locals.runEventStream = options.runEventStream;
  }
  if (options.runExecutor !== undefined) {
    app.locals.runExecutor = options.runExecutor;
  }

  const server = await new Promise<import("node:http").Server>((resolve) => {
    const listeningServer = app.listen(0, "127.0.0.1", () => {
      resolve(listeningServer);
    });
  });

  const address = server.address() as AddressInfo;
  const baseUrl = `http://127.0.0.1:${address.port}`;

  return {
    async getJson(routePath: string) {
      const response = await fetch(`${baseUrl}${routePath}`);
      return {
        status: response.status,
        json: await response.json(),
      };
    },
    async postJson(routePath: string, body: unknown) {
      const response = await fetch(`${baseUrl}${routePath}`, {
        method: "POST",
        headers: {
          "content-type": "application/json",
        },
        body: JSON.stringify(body),
      });
      return {
        status: response.status,
        json: await response.json(),
      };
    },
    async getText(routePath: string) {
      const response = await fetch(`${baseUrl}${routePath}`);
      return {
        status: response.status,
        body: await response.text(),
      };
    },
    async close() {
      await new Promise<void>((resolve, reject) => {
        server.close((error) => {
          if (error) {
            reject(error);
            return;
          }

          resolve();
        });
      });
    },
  };
}

function parseSseFrames(body: string): Array<{ event: string; data: string }> {
  return body
    .trim()
    .split("\n\n")
    .filter((frame) => frame.length > 0)
    .map((frame) => {
      const lines = frame.split("\n");
      const event = lines.find((line) => line.startsWith("event: "));
      const data = lines.find((line) => line.startsWith("data: "));

      if (event === undefined || data === undefined) {
        throw new Error("Invalid SSE frame.");
      }

      return {
        event: event.slice("event: ".length),
        data: data.slice("data: ".length),
      };
    });
}
