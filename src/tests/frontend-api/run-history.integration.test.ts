import { describe, expect, it } from "vitest";
import {
  createEmptyRunEventSafety,
  type CanonicalRunEvent,
} from "../../frontend/contracts.js";
import { createRunHistoryStore } from "../../frontend/run-history/store.js";

describe("run history store", () => {
  it("stores a deterministic ordered per-run trace and final answer", () => {
    const store = createRunHistoryStore();

    store.ingest(
      createEvent({
        run_id: "run-1",
        event_seq: 0,
        event_type: "run_started",
        tool_input: { prompt: "Find sources" },
      }),
    );
    store.ingest(
      createEvent({
        run_id: "run-1",
        event_seq: 1,
        event_type: "tool_call_started",
        tool_name: "web_search",
        tool_call_id: "tool-1",
        tool_input: { query: "agents" },
      }),
    );
    store.ingest(
      createEvent({
        run_id: "run-1",
        event_seq: 2,
        event_type: "final_answer_generated",
        final_answer: "Answer with citations.",
      }),
    );

    const snapshot = store.getRun("run-1");

    expect(snapshot).not.toBeNull();
    expect(snapshot?.finalAnswer).toBe("Answer with citations.");
    expect(snapshot?.events.map((event) => event.event_seq)).toEqual([0, 1, 2]);
    expect(snapshot?.retention.duplicateEventsIgnored).toBe(0);
    expect(snapshot?.retention.outOfOrderEventsRejected).toBe(0);
  });

  it("ignores duplicate event_seq values and rejects lower out-of-order events", () => {
    const store = createRunHistoryStore();
    const duplicate = createEvent({
      run_id: "run-dup",
      event_seq: 1,
      event_type: "tool_call_started",
      tool_name: "web_search",
      tool_call_id: "tool-dup",
      tool_input: { query: "agents" },
    });

    expect(
      store.ingest(
        createEvent({
          run_id: "run-dup",
          event_seq: 0,
          event_type: "run_started",
          tool_input: { prompt: "Prompt" },
        }),
      ).status,
    ).toBe("appended");
    expect(store.ingest(duplicate).status).toBe("appended");
    expect(store.ingest(duplicate).status).toBe("ignored_duplicate");
    expect(
      store.ingest(
        createEvent({
          run_id: "run-dup",
          event_seq: 0,
          event_type: "run_failed",
          error_output: { message: "late" },
        }),
      ).status,
    ).toBe("ignored_duplicate");
    expect(
      store.ingest(
        createEvent({
          run_id: "run-dup",
          event_seq: 3,
          event_type: "run_completed",
          final_answer: "done",
        }),
      ).status,
    ).toBe("appended");
    expect(
      store.ingest(
        createEvent({
          run_id: "run-dup",
          event_seq: 2,
          event_type: "tool_call_succeeded",
          tool_name: "web_search",
          tool_call_id: "tool-dup",
          tool_output: { results: 1 },
        }),
      ).status,
    ).toBe("rejected_out_of_order");

    const snapshot = store.getRun("run-dup");

    expect(snapshot?.events.map((event) => event.event_seq)).toEqual([0, 1, 3]);
    expect(snapshot?.retention.duplicateEventsIgnored).toBe(2);
    expect(snapshot?.retention.outOfOrderEventsRejected).toBe(1);
  });

  it("bounds per-run events and total runs with explicit retention metadata", () => {
    const store = createRunHistoryStore({
      maxRuns: 2,
      maxEventsPerRun: 2,
    });

    store.ingest(createEvent({ run_id: "run-a", event_seq: 0, event_type: "run_started" }));
    store.ingest(createEvent({ run_id: "run-a", event_seq: 1, event_type: "tool_call_started", tool_name: "web_search", tool_call_id: "tool-a" }));
    store.ingest(createEvent({ run_id: "run-a", event_seq: 2, event_type: "run_completed", final_answer: "A" }));

    const firstSnapshot = store.getRun("run-a");
    expect(firstSnapshot?.events.map((event) => event.event_seq)).toEqual([1, 2]);
    expect(firstSnapshot?.retention.eventsDropped).toBe(1);

    store.ingest(createEvent({ run_id: "run-b", event_seq: 0, event_type: "run_started" }));
    store.ingest(createEvent({ run_id: "run-c", event_seq: 0, event_type: "run_started" }));

    expect(store.getRun("run-a")).toBeNull();
    expect(store.listRuns().map((run) => run.runId)).toEqual(["run-c", "run-b"]);
  });

  it("truncates oversized payloads and records truncation metadata for later UI visibility", () => {
    const store = createRunHistoryStore({
      maxPayloadBytes: 180,
    });

    store.ingest(
      createEvent({
        run_id: "run-big",
        event_seq: 0,
        event_type: "tool_call_succeeded",
        tool_name: "web_search",
        tool_call_id: "tool-big",
        tool_output: {
          results: Array.from({ length: 8 }, (_, index) => ({
            position: index + 1,
            snippet: "x".repeat(120),
          })),
        },
      }),
    );

    const snapshot = store.getRun("run-big");
    const event = snapshot?.events[0];

    expect(typeof event?.tool_output).toBe("string");
    expect(event?.tool_output).toContain("Truncated run history payload");
    expect(event?.safety.tool_output.truncation.active).toBe(true);
    expect(event?.safety.tool_output.truncation.paths).toContain("$");
    expect(snapshot?.retention.payloadTruncations).toEqual([
      {
        eventSeq: 0,
        eventType: "tool_call_succeeded",
        fields: ["tool_output"],
        omittedBytes: expect.any(Number),
      },
    ]);
    expect(snapshot?.retention.payloadTruncations[0]?.omittedBytes).toBeGreaterThan(
      0,
    );
  });
});

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
