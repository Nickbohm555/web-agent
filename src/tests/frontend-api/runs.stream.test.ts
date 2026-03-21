import type { AddressInfo } from "node:net";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { RunEventStreamFactory } from "../../frontend/routes/runs.js";

describe("run stream API contracts", () => {
  beforeEach(() => {
    vi.resetModules();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns named SSE frames with validated payloads", async () => {
    const response = await callRunStreamRoute(async function* ({ runId }) {
      yield {
        event: "run_state",
        data: {
          runId,
          state: "running",
          ts: 1_710_000_000_000,
        },
      };
      yield {
        event: "retrieval_action",
        data: {
          runId,
          actionId: "action-1",
          actionType: "search",
          status: "completed",
          query: "Find sources",
          startedAt: 1_710_000_000_050,
          endedAt: 1_710_000_000_150,
          durationMs: 100,
          resultCount: 2,
          outputPreview: "Found two sources",
        },
      };
      yield {
        event: "tool_call",
        data: {
          runId,
          toolCallId: "tool-1",
          toolName: "web_search",
          status: "completed",
          startedAt: 1_710_000_000_000,
          endedAt: 1_710_000_000_300,
          durationMs: 300,
          inputPreview: "Find sources",
          outputPreview: "Found two results",
        },
      };
      yield {
        event: "run_complete",
        data: {
          runId,
          finalAnswer: "Completed answer.",
          sources: [],
          completedAt: 1_710_000_000_500,
          durationMs: 500,
        },
      };
    });

    expect(response.status).toBe(200);
    expect(response.contentType).toContain("text/event-stream");
    expect(response.body).toContain("event: run_state");
    expect(response.body).toContain("event: retrieval_action");
    expect(response.body).toContain("event: tool_call");
    expect(response.body).toContain("event: run_complete");
  });

  it("emits a terminal run_error frame when no stream backend is configured", async () => {
    const { parseRunStreamEvent } = await import("../../frontend/contracts.js");

    const response = await callRunStreamRoute();

    expect(response.status).toBe(200);

    const [frame] = parseSseFrames(response.body);
    expect(frame).toBeDefined();
    if (frame === undefined) {
      throw new Error("Expected a terminal SSE frame.");
    }
    expect(
      parseRunStreamEvent({
        event: frame.event,
        data: JSON.parse(frame.data),
      }),
    ).toMatchObject({
      event: "run_error",
      data: {
        runId: "run-123",
        code: "STREAM_UNAVAILABLE",
      },
    });
  });

  it("starts and completes runs through /api/runs using the configured executor", async () => {
    const { createFrontendServerApp } = await import("../../frontend/server.js");
    const app = createFrontendServerApp();
    const runExecutor = vi.fn(async ({ runId, prompt, mode }) => ({
      status: "completed" as const,
      finalAnswer: `Completed ${mode} run for ${prompt}.`,
      sources: [],
      durationMs: 42,
      completedAt: 1_710_000_000_420,
    }));
    app.locals.runExecutor = runExecutor;

    const server = await new Promise<import("node:http").Server>((resolve) => {
      const listeningServer = app.listen(0, "127.0.0.1", () => {
        resolve(listeningServer);
      });
    });
    const address = server.address() as AddressInfo;

    try {
      const startResponse = await fetch(`http://127.0.0.1:${address.port}/api/runs`, {
        method: "POST",
        headers: {
          "content-type": "application/json",
        },
        body: JSON.stringify({
          prompt: "Find sources",
          mode: "deep_research",
          retrievalPolicy: {
            freshness: "week",
            includeDomains: ["Docs.Example.com"],
            maxAgeMs: 60_000,
            fresh: true,
          },
        }),
      });

      expect(startResponse.status).toBe(201);
      const startPayload = await startResponse.json() as { runId: string };
      const streamResponse = await fetch(
        `http://127.0.0.1:${address.port}/api/runs/${startPayload.runId}/events`,
      );

      expect(streamResponse.status).toBe(200);
      const frames = parseSseFrames(await streamResponse.text());
      expect(frames.map((frame) => frame.event)).toEqual([
        "run_state",
        "run_complete",
      ]);
      expect(runExecutor).toHaveBeenCalledWith({
        runId: startPayload.runId,
        prompt: "Find sources",
        mode: "deep_research",
        retrievalPolicy: {
          search: {
            country: "US",
            language: "en",
            freshness: "week",
            domainScope: {
              includeDomains: ["example.com"],
              excludeDomains: [],
            },
          },
          fetch: {
            maxAgeMs: 60_000,
            fresh: true,
          },
        },
        signal: expect.any(AbortSignal),
      });
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
  });

  it("starts deep-research execution before any SSE client connects", async () => {
    const { createFrontendServerApp } = await import("../../frontend/server.js");
    const app = createFrontendServerApp();
    let resolveRun:
      | ((value: {
        status: "completed";
        finalAnswer: string;
        sources: [];
        durationMs: number;
        completedAt: number;
      }) => void)
      | undefined;
    const runExecutor = vi.fn(() => new Promise((resolve) => {
      resolveRun = resolve;
    }));
    app.locals.runExecutor = runExecutor;

    const server = await new Promise<import("node:http").Server>((resolve) => {
      const listeningServer = app.listen(0, "127.0.0.1", () => {
        resolve(listeningServer);
      });
    });
    const address = server.address() as AddressInfo;

    try {
      const startResponse = await fetch(`http://127.0.0.1:${address.port}/api/runs`, {
        method: "POST",
        headers: {
          "content-type": "application/json",
        },
        body: JSON.stringify({
          prompt: "Investigate background runs",
          mode: "deep_research",
        }),
      });

      expect(startResponse.status).toBe(201);
      const startPayload = await startResponse.json() as { runId: string };
      expect(runExecutor).toHaveBeenCalledTimes(1);
      expect(runExecutor).toHaveBeenCalledWith({
        runId: startPayload.runId,
        prompt: "Investigate background runs",
        mode: "deep_research",
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
        signal: expect.any(AbortSignal),
      });

      resolveRun?.({
        status: "completed",
        finalAnswer: "Background run completed.",
        sources: [],
        durationMs: 120,
        completedAt: 1_710_000_000_120,
      });

      const streamResponse = await fetch(
        `http://127.0.0.1:${address.port}/api/runs/${startPayload.runId}/events`,
      );
      const frames = parseSseFrames(await streamResponse.text());

      expect(frames.map((frame) => frame.event)).toEqual([
        "run_state",
        "run_complete",
      ]);
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
  });
});

describe("run stream client", () => {
  beforeEach(() => {
    vi.resetModules();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("parses typed run events and closes on terminal events", async () => {
    const {
      subscribeToRunEvents,
    } = await import("../../frontend/client/api-client.js");
    const eventSource = new FakeEventSource();
    const handlers = {
      onOpen: vi.fn(),
      onRunState: vi.fn(),
      onRetrievalAction: vi.fn(),
      onToolCall: vi.fn(),
      onRunComplete: vi.fn(),
      onRunError: vi.fn(),
      onInvalidEvent: vi.fn(),
      onTransportError: vi.fn(),
    };

    const subscription = subscribeToRunEvents("run-123", handlers, {
      eventSourceFactory: () => eventSource,
    });

    eventSource.emit("open", new Event("open"));
    eventSource.emitMessage(
      "run_state",
      JSON.stringify({
        runId: "run-123",
        state: "running",
        ts: 10,
      }),
    );
    eventSource.emitMessage(
      "retrieval_action",
      JSON.stringify({
        runId: "run-123",
        actionId: "action-1",
        actionType: "open_page",
        status: "completed",
        url: "https://example.com/release-notes",
        startedAt: 10,
        endedAt: 11,
        durationMs: 1,
        title: "Release notes",
      }),
    );
    eventSource.emitMessage(
      "tool_call",
      JSON.stringify({
        runId: "run-123",
        toolCallId: "tool-1",
        toolName: "web_crawl",
        status: "started",
        startedAt: 11,
      }),
    );
    eventSource.emitMessage(
      "run_complete",
      JSON.stringify({
        runId: "run-123",
        finalAnswer: "Done",
        sources: [],
        completedAt: 20,
        durationMs: 10,
      }),
    );

    expect(handlers.onOpen).toHaveBeenCalledTimes(1);
    expect(handlers.onRunState).toHaveBeenCalledWith({
      runId: "run-123",
      state: "running",
      ts: 10,
    });
    expect(handlers.onRetrievalAction).toHaveBeenCalledWith({
      runId: "run-123",
      actionId: "action-1",
      actionType: "open_page",
      status: "completed",
      url: "https://example.com/release-notes",
      startedAt: 10,
      endedAt: 11,
      durationMs: 1,
      title: "Release notes",
    });
    expect(handlers.onToolCall).toHaveBeenCalledWith({
      runId: "run-123",
      toolCallId: "tool-1",
      toolName: "web_crawl",
      status: "started",
      startedAt: 11,
    });
    expect(handlers.onRunComplete).toHaveBeenCalledWith({
      runId: "run-123",
      finalAnswer: "Done",
      sources: [],
      completedAt: 20,
      durationMs: 10,
    });
    expect(handlers.onRunError).not.toHaveBeenCalled();
    expect(handlers.onInvalidEvent).not.toHaveBeenCalled();
    expect(eventSource.closeCount).toBe(1);

    subscription.close();
    expect(eventSource.closeCount).toBe(1);
  });

  it("parses citation-aware completion payloads and forwards structured sources", async () => {
    const {
      subscribeToRunEvents,
    } = await import("../../frontend/client/api-client.js");
    const eventSource = new FakeEventSource();
    const handlers = {
      onRunComplete: vi.fn(),
      onInvalidEvent: vi.fn(),
    };

    subscribeToRunEvents("run-123", handlers, {
      eventSourceFactory: () => eventSource,
    });

    eventSource.emitMessage(
      "run_complete",
      JSON.stringify({
        runId: "run-123",
        finalAnswer: "Alpha remains ahead of Beta.",
        structuredAnswer: {
          text: "Alpha remains ahead of Beta.",
          citations: [
            {
              source_id: "alpha-report",
              title: "Alpha report",
              url: "https://example.com/alpha",
              start_index: 0,
              end_index: 5,
            },
          ],
        },
        sources: [
          {
            source_id: "alpha-report",
            title: "Alpha report",
            url: "https://example.com/alpha",
            snippet: "Alpha evidence.",
          },
        ],
        completedAt: 20,
        durationMs: 10,
      }),
    );

    expect(handlers.onRunComplete).toHaveBeenCalledWith({
      runId: "run-123",
      finalAnswer: "Alpha remains ahead of Beta.",
      structuredAnswer: {
        text: "Alpha remains ahead of Beta.",
        citations: [
          {
            source_id: "alpha-report",
            title: "Alpha report",
            url: "https://example.com/alpha",
            start_index: 0,
            end_index: 5,
          },
        ],
      },
      sources: [
        {
          source_id: "alpha-report",
          title: "Alpha report",
          url: "https://example.com/alpha",
          snippet: "Alpha evidence.",
        },
      ],
      completedAt: 20,
      durationMs: 10,
    });
    expect(handlers.onInvalidEvent).not.toHaveBeenCalled();
    expect(eventSource.closeCount).toBe(1);
  });

  it("rejects malformed citation-rich completion payloads without crashing the stream client", async () => {
    const {
      subscribeToRunEvents,
    } = await import("../../frontend/client/api-client.js");
    const eventSource = new FakeEventSource();
    const handlers = {
      onRunComplete: vi.fn(),
      onInvalidEvent: vi.fn(),
    };

    subscribeToRunEvents("run-123", handlers, {
      eventSourceFactory: () => eventSource,
    });

    eventSource.emitMessage(
      "run_complete",
      JSON.stringify({
        runId: "run-123",
        finalAnswer: "Broken citation payload.",
        structuredAnswer: {
          text: "Broken citation payload.",
          citations: [
            {
              source_id: "broken-source",
              title: "",
              url: "not-a-url",
              start_index: 7,
              end_index: 3,
            },
          ],
        },
        sources: [
          {
            source_id: "broken-source",
            title: "",
            url: "not-a-url",
            snippet: "Broken evidence.",
          },
        ],
        completedAt: 20,
        durationMs: 10,
      }),
    );

    expect(handlers.onRunComplete).not.toHaveBeenCalled();
    expect(handlers.onInvalidEvent).toHaveBeenCalledTimes(1);
    expect(eventSource.closeCount).toBe(0);
  });

  it("ignores malformed frames without crashing and closes superseded streams", async () => {
    const {
      subscribeToRunEvents,
    } = await import("../../frontend/client/api-client.js");
    const firstEventSource = new FakeEventSource();
    const secondEventSource = new FakeEventSource();
    const invalidEventHandler = vi.fn();

    subscribeToRunEvents(
      "run-123",
      {
        onInvalidEvent: invalidEventHandler,
      },
      {
        eventSourceFactory: () => firstEventSource,
      },
    );

    firstEventSource.emitMessage(
      "tool_call",
      JSON.stringify({
        runId: "run-123",
        toolCallId: "tool-1",
        toolName: "web_search",
        status: "completed",
        durationMs: -1,
      }),
    );

    expect(invalidEventHandler).toHaveBeenCalledTimes(1);
    expect(firstEventSource.closeCount).toBe(0);

    subscribeToRunEvents(
      "run-456",
      {
        onInvalidEvent: invalidEventHandler,
      },
      {
        eventSourceFactory: () => secondEventSource,
      },
    );

    expect(firstEventSource.closeCount).toBe(1);
    expect(secondEventSource.closeCount).toBe(0);
  });
});

async function callRunStreamRoute(
  runEventStream?: RunEventStreamFactory,
): Promise<{ status: number; contentType: string; body: string }> {
  const { createFrontendServerApp } = await import("../../frontend/server.js");
  const app = createFrontendServerApp();

  if (runEventStream !== undefined) {
    app.locals.runEventStream = runEventStream;
  }

  const server = await new Promise<import("node:http").Server>((resolve) => {
    const listeningServer = app.listen(0, "127.0.0.1", () => {
      resolve(listeningServer);
    });
  });

  const address = server.address() as AddressInfo;

  try {
    const response = await fetch(
      `http://127.0.0.1:${address.port}/api/runs/run-123/events`,
    );

    return {
      status: response.status,
      contentType: response.headers.get("content-type") ?? "",
      body: await response.text(),
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

class FakeEventSource {
  private readonly listeners = new Map<
    string,
    Set<(event: Event | MessageEvent<string>) => void>
  >();

  closeCount = 0;

  addEventListener(
    type: string,
    listener: (event: Event | MessageEvent<string>) => void,
  ): void {
    const listeners = this.listeners.get(type) ?? new Set();
    listeners.add(listener);
    this.listeners.set(type, listeners);
  }

  removeEventListener(
    type: string,
    listener: (event: Event | MessageEvent<string>) => void,
  ): void {
    this.listeners.get(type)?.delete(listener);
  }

  close(): void {
    this.closeCount += 1;
  }

  emit(type: string, event: Event | MessageEvent<string>): void {
    for (const listener of this.listeners.get(type) ?? []) {
      listener(event);
    }
  }

  emitMessage(type: string, data: string): void {
    const event = new MessageEvent<string>(type, { data });
    this.emit(type, event);
  }
}
