import type { AddressInfo } from "node:net";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { parseRunEventList } from "../../frontend/contracts.js";
import { toRunEventTimelineRows } from "../../frontend/client/timeline.js";

const searchMock = vi.fn();
const fetchMock = vi.fn();

vi.mock("../../sdk/search.js", () => ({
  search: searchMock,
}));

vi.mock("../../sdk/fetch.js", () => ({
  fetch: fetchMock,
}));

describe("observability correlation context", () => {
  beforeEach(() => {
    searchMock.mockReset();
    fetchMock.mockReset();
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
    expect(eventSeqs).toEqual([1, 2, 3, 4]);

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
      1, 2, 3, 4,
    ]);
    expect(capturedRuns[1]?.map((event) => event.event_seq)).toEqual([
      1, 2, 3, 4,
    ]);
    expect(capturedRuns[0]?.[0]?.run_id).not.toBe(capturedRuns[1]?.[0]?.run_id);
  });

  it("emits structured observability events for search and fetch without leaking secrets", async () => {
    searchMock.mockResolvedValueOnce(
      createSearchResponse({
        snippet:
          "x".repeat(320),
      }),
    );
    fetchMock.mockRejectedValueOnce(new Error("validation failure"));

    const stdoutSpy = vi
      .spyOn(process.stdout, "write")
      .mockImplementation(() => true);

    const searchResponse = await callRoute("/api/search", {
      query: "agents",
      options: {
        includeDomains: ["example.com"],
      },
    });
    const fetchResponse = await callRoute("/api/fetch", {
      url: "https://example.com/private",
      apiKey: "secret-api-key",
      token: "secret-token",
    });

    expect(searchResponse.status).toBe(200);
    expect(fetchResponse.status).toBe(400);

    const parsedEvents = parseStructuredLogEvents(stdoutSpy.mock.calls);
    expect(parsedEvents).toHaveLength(3);

    expect(parsedEvents.map((event) => event.event_type)).toEqual([
      "tool_call_started",
      "tool_call_succeeded",
      "tool_call_failed",
    ]);

    for (const event of parsedEvents) {
      expect(event.run_id).toEqual(expect.any(String));
      expect(event.run_id.length).toBeGreaterThan(0);
    }

    expect(parsedEvents[0]?.event_seq).toBe(0);
    expect(parsedEvents[1]?.event_seq).toBe(1);
    expect(parsedEvents[2]?.event_seq).toBe(0);

    expect(parsedEvents[0]?.tool_name).toBe("web_search");
    expect(parsedEvents[1]?.tool_name).toBe("web_search");
    expect(parsedEvents[2]?.tool_name).toBe("web_crawl");

    expect(parsedEvents[1]?.tool_output).toEqual({
      ...createSearchResponse({
        snippet: `${"x".repeat(256)}[Truncated]`,
      }),
    });
    expect(parsedEvents[1]?.safety.tool_output.truncation.active).toBe(true);
    expect(parsedEvents[1]?.safety.tool_output.truncation.paths).toContain(
      "results.0.snippet",
    );

    expect(parsedEvents[2]?.tool_input).toEqual({
      url: "https://example.com/private",
      apiKey: "[Redacted]",
      token: "[Redacted]",
    });
    expect(parsedEvents[2]?.safety.tool_input.redaction.paths).toEqual([
      "apiKey",
      "token",
    ]);
    expect(parsedEvents[2]?.error_output).toEqual({
      statusCode: 400,
      error: {
        code: "VALIDATION_ERROR",
        message: "Request payload failed validation.",
        details: {
          formErrors: ["Unrecognized keys: \"apiKey\", \"token\""],
          fieldErrors: {},
        },
      },
    });

    const serializedLogs = stdoutSpy.mock.calls
      .map(([chunk]) => String(chunk))
      .join("");
    expect(serializedLogs).not.toContain("secret-api-key");
    expect(serializedLogs).not.toContain("secret-token");
  });

  it("maintains one-to-one parity between frontend timeline rows and backend log events", async () => {
    searchMock.mockResolvedValueOnce(createSearchResponse());

    const stdoutSpy = vi
      .spyOn(process.stdout, "write")
      .mockImplementation(() => true);

    const response = await callRoute("/api/search", {
      query: "timeline parity",
    });

    expect(response.status).toBe(200);

    const backendEvents = parseStructuredLogEvents(stdoutSpy.mock.calls);
    expect(backendEvents.map((event) => event.event_type)).toEqual([
      "tool_call_started",
      "tool_call_succeeded",
    ]);

    const frontendEvents = parseRunEventList(backendEvents);
    const timelineRows = toRunEventTimelineRows(frontendEvents);

    expect(timelineRows).toHaveLength(backendEvents.length);

    for (const [index, row] of timelineRows.entries()) {
      const backendEvent = backendEvents[index];
      expect(backendEvent).toBeDefined();
      expect(row.eventKey).toBe(
        `${backendEvent?.run_id}:${backendEvent?.event_seq}`,
      );
      expect(row.eventSeq).toBe(backendEvent?.event_seq);
      expect(row.eventType).toBe(backendEvent?.event_type);
    }

    const parityKeys = new Set(
      backendEvents.map(
        (event) => `${event.run_id}:${event.event_seq}:${event.event_type}`,
      ),
    );
    const timelineKeys = new Set(
      timelineRows.map((row) => `${row.eventKey}:${row.eventType}`),
    );

    expect(timelineKeys).toEqual(parityKeys);
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

async function callRoute(
  routePath: "/api/search" | "/api/fetch",
  payload: unknown,
): Promise<{
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
    const response = await fetch(`http://127.0.0.1:${address.port}${routePath}`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
      },
      body: JSON.stringify(payload),
    });

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

function parseStructuredLogEvents(
  calls: Array<[chunk: unknown, ...args: unknown[]]>,
) {
  const records = calls.flatMap(([chunk]) =>
    String(chunk)
      .split("\n")
      .map((line) => line.trim())
      .filter((line) => line.length > 0)
      .map((line) => {
        try {
          return JSON.parse(line);
        } catch {
          return null;
        }
      })
      .filter((record): record is Record<string, unknown> => record !== null),
  );

  return parseRunEventList(
    records
      .filter((record) => typeof record.event_type === "string")
      .map((record) => ({
        run_id: record.run_id,
        event_seq: record.event_seq,
        event_type: record.event_type,
        ts: record.ts,
        tool_name: record.tool_name,
        tool_call_id: record.tool_call_id,
        tool_input: record.tool_input,
        tool_output: record.tool_output,
        error_output: record.error_output,
        final_answer: record.final_answer,
        safety: record.safety,
      })),
  );
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

function createSearchResponse(overrides?: { snippet?: string }) {
  return {
    query: "agents",
    results: [
      {
        title: "Agents overview",
        url: "https://example.com/agents",
        snippet: overrides?.snippet ?? "summary",
        rank: {
          position: 1,
          providerPosition: 1,
        },
      },
    ],
    meta: {
      operation: "search" as const,
      durationMs: 1,
      attempts: 1,
      retries: 0,
      cacheHit: false,
      timings: {},
    },
    metadata: {
      resultCount: 1,
    },
  };
}
