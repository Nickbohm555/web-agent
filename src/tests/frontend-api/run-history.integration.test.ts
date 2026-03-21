import type { AddressInfo } from "node:net";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  parseRunHistoryListResponse,
  parseRunHistoryNotFoundError,
  parseRunHistoryRunSnapshot,
  type RunStreamEvent,
} from "../../frontend/contracts.js";
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
        eventCount: 5,
        latestEventSeq: 4,
      });

      const detailResponse = await harness.getJson(`/api/runs/${runId}/history`);
      expect(detailResponse.status).toBe(200);
      const detailPayload = parseRunHistoryRunSnapshot(detailResponse.json);
      expect(detailPayload.runId).toBe(runId);
      expect(detailPayload.finalAnswer).toBe("Answer with citations.");
      expect(detailPayload.events.map((event) => event.event_seq)).toEqual([
        0, 1, 2, 3, 4,
      ]);
      expect(detailPayload.events.map((event) => event.event_type)).toEqual([
        "run_started",
        "tool_call_started",
        "tool_call_succeeded",
        "final_answer_generated",
        "run_completed",
      ]);
      expect(detailPayload.events[0]?.tool_input).toEqual({
        prompt: "Find sources",
        mode: "quick",
        retrievalPolicy: {
          search: {
            country: "US",
            language: "en",
            freshness: "any",
            domainScope: {
              includeDomains: [],
              excludeDomains: [],
            },
          },
          fetch: {
            maxAgeMs: 300_000,
            fresh: false,
          },
        },
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
            toolName: "web_crawl",
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
        mode: "deep_research",
      });
      const runId = parseRunId(startResponse.json);

      await harness.getText(`/api/runs/${runId}/events`);

      const detailResponse = await harness.getJson(`/api/runs/${runId}/history`);
      const detailPayload = parseRunHistoryRunSnapshot(detailResponse.json);

      expect(detailPayload.events.map((event) => event.event_seq)).toEqual([
        3, 4, 5,
      ]);
      expect(detailPayload.retention.eventsDropped).toBe(3);
      expect(detailPayload.retention.payloadTruncations.length).toBeGreaterThan(0);
      expect(detailPayload.retention.payloadTruncations.some((entry) => {
        return entry.fields.includes("tool_input") || entry.fields.includes("tool_output");
      })).toBe(true);
      expect(detailPayload.finalAnswer).toContain("[Truncated run history answer]");
    } finally {
      await harness.close();
    }
  });

  it("persists deep-research progress before the run stream is consumed", async () => {
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
        prompt: "Investigate deep research",
        mode: "deep_research",
      });
      expect(startResponse.status).toBe(201);

      const runId = parseRunId(startResponse.json);
      await new Promise((resolve) => setTimeout(resolve, 8));

      const detailBeforeStream = await harness.getJson(`/api/runs/${runId}/history`);
      expect(detailBeforeStream.status).toBe(200);
      const snapshotBeforeStream = parseRunHistoryRunSnapshot(detailBeforeStream.json);
      expect(snapshotBeforeStream.events.map((event) => event.event_type)).toEqual([
        "run_started",
        "tool_call_started",
        "tool_call_succeeded",
      ]);

      allowCompletion();
      await new Promise((resolve) => setTimeout(resolve, 8));

      const streamText = await harness.getText(`/api/runs/${runId}/events`);
      expect(streamText.status).toBe(200);
      expect(parseSseFrames(streamText.body).map((frame) => frame.event)).toEqual([
        "run_state",
        "tool_call",
        "tool_call",
        "run_complete",
      ]);

      const detailAfterStream = await harness.getJson(`/api/runs/${runId}/history`);
      const snapshotAfterStream = parseRunHistoryRunSnapshot(detailAfterStream.json);
      expect(snapshotAfterStream.events.map((event) => event.event_type)).toEqual([
        "run_started",
        "tool_call_started",
        "tool_call_succeeded",
        "final_answer_generated",
        "run_completed",
      ]);
      expect(snapshotAfterStream.finalAnswer).toBe("Long-running answer.");
    } finally {
      await harness.close();
    }
  });

  it("rejects deep-research starts once the active background-run cap is reached", async () => {
    const harness = await createHarness({
      runEventStream: async function* () {
        await new Promise(() => {});
      },
    });

    try {
      const acceptedResponses = await Promise.all(
        Array.from({ length: 3 }, () =>
          harness.postJson("/api/runs", {
            prompt: "Concurrency check",
            mode: "deep_research",
          }),
        ),
      );

      expect(acceptedResponses.map((response) => response.status)).toEqual([
        201, 201, 201,
      ]);

      const rejectedResponse = await harness.postJson("/api/runs", {
        prompt: "Concurrency check",
        mode: "deep_research",
      });

      expect(rejectedResponse.status).toBe(429);
      expect(rejectedResponse.json).toMatchObject({
        ok: false,
        operation: "run_start",
        error: {
          code: "RATE_LIMITED",
          message: "Too many deep research runs are already active.",
          details: {
            kind: "rate_limited",
            retryable: true,
          },
        },
      });
    } finally {
      await harness.close();
    }
  });
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
} = {}) {
  const { createFrontendServerApp } = await import("../../frontend/server.js");
  const app = createFrontendServerApp();
  app.locals.runHistoryStore = options.store ?? createRunHistoryStore();
  if (options.runEventStream !== undefined) {
    app.locals.runEventStream = options.runEventStream;
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
