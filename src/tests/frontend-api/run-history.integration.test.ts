import type { AddressInfo } from "node:net";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  createEmptyRunEventSafety,
  parseRunHistoryListResponse,
  parseRunHistoryNotFoundError,
  parseRunHistoryRunSnapshot,
  type CanonicalRunEvent,
} from "../../frontend/contracts.js";
import { createRunHistoryStore } from "../../frontend/run-history/store.js";

describe("run history API", () => {
  beforeEach(() => {
    vi.resetModules();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns empty history list responses and a typed not-found detail response", async () => {
    const response = await callRoute("/api/runs/history");

    expect(response.status).toBe(200);
    expect(parseRunHistoryListResponse(response.json)).toEqual({
      runs: [],
    });

    const notFoundResponse = await callRoute("/api/runs/run-missing/history");

    expect(notFoundResponse.status).toBe(404);
    expect(parseRunHistoryNotFoundError(notFoundResponse.json)).toEqual({
      error: {
        code: "RUN_HISTORY_NOT_FOUND",
        message: "Run history for 'run-missing' was not found.",
      },
    });
  });

  it("returns per-run summaries and detail snapshots with final answer and ordered events", async () => {
    const store = createRunHistoryStore();
    store.ingest(
      createEvent({
        run_id: "run-older",
        event_seq: 0,
        event_type: "run_started",
        tool_input: { prompt: "Older prompt" },
      }),
    );
    store.ingest(
      createEvent({
        run_id: "run-current",
        event_seq: 0,
        event_type: "run_started",
        tool_input: { prompt: "Find sources" },
      }),
    );
    store.ingest(
      createEvent({
        run_id: "run-current",
        event_seq: 1,
        event_type: "tool_call_started",
        tool_name: "web_search",
        tool_call_id: "tool-1",
        tool_input: { query: "agents" },
      }),
    );
    store.ingest(
      createEvent({
        run_id: "run-current",
        event_seq: 2,
        event_type: "final_answer_generated",
        final_answer: "Answer with citations.",
      }),
    );

    const listResponse = await callRoute("/api/runs/history", store);

    expect(listResponse.status).toBe(200);
    const listPayload = parseRunHistoryListResponse(listResponse.json);
    expect(listPayload.runs).toHaveLength(2);
    expect(listPayload.runs.map((run) => run.runId)).toEqual([
      "run-current",
      "run-older",
    ]);
    expect(listPayload.runs[0]).toMatchObject({
      runId: "run-current",
      finalAnswer: "Answer with citations.",
      eventCount: 3,
      latestEventSeq: 2,
      retention: {
        duplicateEventsIgnored: 0,
        outOfOrderEventsRejected: 0,
        eventsDropped: 0,
      },
    });

    const detailResponse = await callRoute(
      "/api/runs/run-current/history",
      store,
    );

    expect(detailResponse.status).toBe(200);
    const detailPayload = parseRunHistoryRunSnapshot(detailResponse.json);
    expect(detailPayload.runId).toBe("run-current");
    expect(detailPayload.finalAnswer).toBe("Answer with citations.");
    expect(detailPayload.events.map((event) => event.event_seq)).toEqual([
      0, 1, 2,
    ]);
    expect(detailPayload.events.at(-1)?.final_answer).toBe(
      "Answer with citations.",
    );
    expect(detailPayload.retention.payloadTruncations).toEqual([]);
  });
});

async function callRoute(
  routePath: string,
  store = createRunHistoryStore(),
): Promise<{ status: number; json: unknown }> {
  const { createFrontendServerApp } = await import("../../frontend/server.js");
  const app = createFrontendServerApp();
  app.locals.runHistoryStore = store;

  const server = await new Promise<import("node:http").Server>((resolve) => {
    const listeningServer = app.listen(0, "127.0.0.1", () => {
      resolve(listeningServer);
    });
  });

  const address = server.address() as AddressInfo;

  try {
    const response = await fetch(`http://127.0.0.1:${address.port}${routePath}`);

    return {
      status: response.status,
      json: await response.json(),
    };
  } finally {
    await new Promise<void>((resolve, reject) => {
      server.close((error) => {
        if (error) {
          reject(error);
          return;
        }

        resolve();
      });
    });
  }
}

function createEvent(
  event: Partial<CanonicalRunEvent> &
    Pick<CanonicalRunEvent, "run_id" | "event_seq" | "event_type">,
): CanonicalRunEvent {
  return {
    ts: "2026-03-17T00:00:00.000Z",
    safety: createEmptyRunEventSafety(),
    ...event,
  };
}
