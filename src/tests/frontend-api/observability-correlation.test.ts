import type { AddressInfo } from "node:net";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const searchMock = vi.fn();

vi.mock("../../sdk/search.js", () => ({
  search: searchMock,
}));

describe("observability correlation context", () => {
  beforeEach(() => {
    searchMock.mockReset();
    vi.resetModules();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("assigns one non-empty run_id and strictly increasing event_seq values per API run", async () => {
    let events: Array<{ run_id: string; event_seq: number }> = [];
    searchMock.mockImplementation(async () => {
      events = await captureCorrelationEvents();
      return createSearchResponse();
    });

    const response = await callSearchRoute();

    expect(response.status).toBe(200);
    expect(events).toHaveLength(4);

    const runIds = new Set(events.map((event) => event.run_id));
    expect(runIds.size).toBe(1);
    expect(events[0]?.run_id).toEqual(expect.any(String));
    expect(events[0]?.run_id.length).toBeGreaterThan(0);

    const eventSeqs = events.map((event) => event.event_seq);
    expect(eventSeqs).toEqual([0, 1, 2, 3]);

    const pairKeys = new Set(
      events.map((event) => `${event.run_id}:${event.event_seq}`),
    );
    expect(pairKeys.size).toBe(events.length);
  });

  it("resets sequencing for each new run context", async () => {
    const capturedRuns: Array<Array<{ run_id: string; event_seq: number }>> = [];
    searchMock.mockImplementation(async () => {
      capturedRuns.push(await captureCorrelationEvents());
      return createSearchResponse();
    });

    const firstResponse = await callSearchRoute();
    const secondResponse = await callSearchRoute();

    expect(firstResponse.status).toBe(200);
    expect(secondResponse.status).toBe(200);

    expect(capturedRuns[0]?.map((event) => event.event_seq)).toEqual([
      0, 1, 2, 3,
    ]);
    expect(capturedRuns[1]?.map((event) => event.event_seq)).toEqual([
      0, 1, 2, 3,
    ]);
    expect(capturedRuns[0]?.[0]?.run_id).not.toBe(capturedRuns[1]?.[0]?.run_id);
  });
});

async function callSearchRoute(): Promise<{
  status: number;
  json: unknown;
}> {
  const { createFrontendServerApp } = await import("../../frontend/server.js");
  const app = createFrontendServerApp();

  const server = await new Promise<import("node:http").Server>((resolve) => {
    const listeningServer = app.listen(0, "127.0.0.1", () => {
      resolve(listeningServer);
    });
  });

  const address = server.address() as AddressInfo;

  try {
    const response = await fetch(
      `http://127.0.0.1:${address.port}/api/search`,
      {
        method: "POST",
        headers: {
          "content-type": "application/json",
        },
        body: JSON.stringify({
          query: "agents",
        }),
      },
    );

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

async function captureCorrelationEvents(): Promise<
  Array<{ run_id: string; event_seq: number }>
> {
  const {
    getRunContext,
    nextRunEventSequence,
  } = await import("../../core/telemetry/run-context.js");
  const firstContext = getRunContext();
  if (firstContext === null) {
    throw new Error("Expected run context at API entrypoint.");
  }

  const correlationEvents = [
    {
      run_id: firstContext.run_id,
      event_seq: nextRunEventSequence(),
    },
  ];

  await Promise.resolve();
  const secondContext = getRunContext();
  if (secondContext === null) {
    throw new Error("Expected run context after promise boundary.");
  }
  correlationEvents.push({
    run_id: secondContext.run_id,
    event_seq: nextRunEventSequence(),
  });

  await new Promise<void>((resolve) => {
    setTimeout(resolve, 0);
  });
  const thirdContext = getRunContext();
  if (thirdContext === null) {
    throw new Error("Expected run context after timer boundary.");
  }
  correlationEvents.push({
    run_id: thirdContext.run_id,
    event_seq: nextRunEventSequence(),
  });

  await new Promise<void>((resolve) => {
    setImmediate(resolve);
  });
  const fourthContext = getRunContext();
  if (fourthContext === null) {
    throw new Error("Expected run context after immediate boundary.");
  }
  correlationEvents.push({
    run_id: fourthContext.run_id,
    event_seq: nextRunEventSequence(),
  });

  return correlationEvents;
}

function createSearchResponse() {
  return {
    query: "agents",
    results: [],
    meta: {
      operation: "search" as const,
      durationMs: 1,
      attempts: 1,
      retries: 0,
      cacheHit: false,
      timings: {},
    },
    metadata: {
      resultCount: 0,
    },
  };
}
