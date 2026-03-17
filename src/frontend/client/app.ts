import {
  createEmptyRunEventSafety,
  createRunEventKey,
  parseOrderedRunEventList,
  type CanonicalRunEvent,
} from "../contracts.js";
import {
  createRun,
  subscribeToRunEvents,
  type RunStreamSubscription,
} from "./api-client.js";
import { initialRunState, reduceRunState, type RunState } from "./state.js";
import { toRunEventTimelineRows } from "./timeline.js";

const promptInput = requireElement<HTMLInputElement>("prompt-input");
const promptError = requireElement<HTMLElement>("prompt-error");
const runForm = requireElement<HTMLFormElement>("run-form");
const runButton = requireElement<HTMLButtonElement>("run-submit");
const previewButton = requireElement<HTMLButtonElement>("preview-events");
const runStatus = requireElement<HTMLElement>("run-status");
const runDetails = requireElement<HTMLElement>("run-details");
const timelineEmpty = requireElement<HTMLElement>("timeline-empty");
const timelineList = requireElement<HTMLElement>("timeline-list");
const inspectorEmpty = requireElement<HTMLElement>("inspector-empty");
const inspectorHeader = requireElement<HTMLElement>("inspector-header");
const inspectorMeta = requireElement<HTMLElement>("inspector-meta");
const inspectorInput = requireElement<HTMLElement>("payload-input");
const inspectorOutput = requireElement<HTMLElement>("payload-output");
const inspectorError = requireElement<HTMLElement>("payload-error");
const inspectorFinalAnswer = requireElement<HTMLElement>("payload-final-answer");

let state = initialRunState;
let streamSubscription: RunStreamSubscription | null = null;
let durationTimer: number | null = null;

render();

promptInput.addEventListener("input", () => {
  dispatch({
    type: "prompt_updated",
    prompt: promptInput.value,
  });
});

previewButton.addEventListener("click", () => {
  closeRunStream();
  dispatch({
    type: "preview_events_loaded",
    events: createPreviewEvents(),
  });
});

runForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const prompt = promptInput.value.trim();
  dispatch({
    type: "prompt_updated",
    prompt,
  });

  if (prompt.length === 0) {
    dispatch({
      type: "run_failed",
      message: "Prompt is required.",
    });
    return;
  }

  closeRunStream();
  dispatch({ type: "run_requested" });

  const result = await createRun({ prompt });
  if (result.ok) {
    dispatch({
      type: "run_started",
      response: result.data,
    });
    openRunStream(result.data.runId);
    return;
  }

  dispatch({
    type: "run_failed",
    message: result.message,
  });
});

function dispatch(action: Parameters<typeof reduceRunState>[1]) {
  state = reduceRunState(state, action);
  render();
}

function render() {
  promptInput.value = state.prompt;
  runButton.disabled = state.phase === "starting" || state.phase === "running";

  promptError.textContent =
    state.phase === "failed" && state.prompt.length === 0
      ? state.error
      : "";

  runStatus.textContent = statusLabel(state);
  runStatus.dataset.phase = state.phase;

  runDetails.textContent = detailsLabel(state);
  renderTimeline();
  renderInspector();
  syncDurationTimer();
}

function statusLabel(currentState: RunState): string {
  switch (currentState.phase) {
    case "idle":
      return "Idle";
    case "starting":
      return "Starting";
    case "running":
      return "Running";
    case "completed":
      return "Completed";
    case "failed":
      return "Failed";
  }
}

function detailsLabel(currentState: RunState): string {
  if (currentState.runEvents.length > 0) {
    return "Select a timeline event to inspect full payloads and safety markers.";
  }

  switch (currentState.phase) {
    case "idle":
      return "Enter a prompt to start one run, or load the payload preview.";
    case "starting":
      return "Creating run...";
    case "running":
      return currentState.activeRunId === null
        ? "Run active."
        : `Run ${currentState.activeRunId} is active. Waiting for event payloads.`;
    case "completed":
      return currentState.finalAnswer ?? "Run completed.";
    case "failed":
      return currentState.error ?? "Run could not be started.";
  }
}

function renderTimeline() {
  const rows = toRunEventTimelineRows(state.runEvents);
  timelineEmpty.hidden = rows.length > 0;

  timelineList.replaceChildren(
    ...rows.map((row) => {
      const item = document.createElement("li");
      item.className = "timeline-item";

      const button = document.createElement("button");
      button.className = "timeline-row";
      button.type = "button";
      button.dataset.eventType = row.eventType;
      button.dataset.selected = String(row.eventKey === state.selectedEventKey);
      button.addEventListener("click", () => {
        dispatch({
          type: "run_event_selected",
          eventKey: row.eventKey,
        });
      });

      const primary = document.createElement("div");
      primary.className = "timeline-primary";

      const eventType = document.createElement("p");
      eventType.className = "timeline-tool";
      eventType.textContent =
        row.toolName === null ? row.eventTypeLabel : `${row.eventTypeLabel} / ${row.toolName}`;

      const meta = document.createElement("p");
      meta.className = "timeline-meta";
      meta.textContent = `#${row.eventSeq} at ${row.timestampLabel}`;

      primary.append(eventType, meta);

      const badges = document.createElement("div");
      badges.className = "timeline-badges";

      const eventBadge = document.createElement("span");
      eventBadge.className = "timeline-badge";
      eventBadge.dataset.kind = "event";
      eventBadge.textContent = row.eventTypeLabel;
      badges.append(eventBadge);

      for (const indicator of row.safetyIndicators) {
        const indicatorBadge = document.createElement("span");
        indicatorBadge.className = "timeline-badge";
        indicatorBadge.dataset.kind = indicator.includes("redacted")
          ? "redaction"
          : "truncation";
        indicatorBadge.textContent = indicator;
        badges.append(indicatorBadge);
      }

      button.append(primary, badges);
      item.append(button);
      return item;
    }),
  );
}

function renderInspector() {
  const selectedEvent = state.runEvents.find(
    (event) => createRunEventKey(event) === state.selectedEventKey,
  );

  inspectorEmpty.hidden = selectedEvent !== undefined;

  if (selectedEvent === undefined) {
    inspectorHeader.textContent = "Select a timeline event";
    inspectorMeta.textContent =
      "Tool input, output, and error payloads appear here with safety markers.";
    renderPayloadSlot(inspectorInput, "Input payload", undefined, undefined);
    renderPayloadSlot(inspectorOutput, "Output payload", undefined, undefined);
    renderPayloadSlot(inspectorError, "Error payload", undefined, undefined);
    renderFinalAnswer(undefined);
    return;
  }

  inspectorHeader.textContent = selectedEvent.tool_name
    ? `${selectedEvent.event_type} / ${selectedEvent.tool_name}`
    : selectedEvent.event_type;
  inspectorMeta.textContent = `run_id ${selectedEvent.run_id} · event_seq ${selectedEvent.event_seq} · ${selectedEvent.ts}`;

  renderPayloadSlot(
    inspectorInput,
    "Input payload",
    selectedEvent.tool_input,
    selectedEvent.safety.tool_input,
  );
  renderPayloadSlot(
    inspectorOutput,
    "Output payload",
    selectedEvent.tool_output,
    selectedEvent.safety.tool_output,
  );
  renderPayloadSlot(
    inspectorError,
    "Error payload",
    selectedEvent.error_output,
    selectedEvent.safety.error_output,
  );
  renderFinalAnswer(selectedEvent.final_answer);
}

function syncDurationTimer() {
  if (state.phase === "running") {
    if (durationTimer === null) {
      durationTimer = window.setInterval(() => {
        renderTimeline();
      }, 200);
    }
    return;
  }

  if (durationTimer !== null) {
    window.clearInterval(durationTimer);
    durationTimer = null;
  }
}

function openRunStream(runId: string) {
  streamSubscription = subscribeToRunEvents(runId, {
    onRunState: (event) => {
      dispatch({
        type: "run_state_received",
        event,
      });
    },
    onToolCall: (event) => {
      dispatch({
        type: "tool_call_received",
        event,
      });
    },
    onRunComplete: (event) => {
      dispatch({
        type: "run_completed",
        event,
      });
      closeRunStream();
    },
    onRunError: (event) => {
      dispatch({
        type: "run_error_received",
        event,
      });
      closeRunStream();
    },
    onInvalidEvent: () => {
      dispatch({
        type: "run_failed",
        message: "Run stream returned an invalid event.",
      });
      closeRunStream();
    },
    onTransportError: () => {
      if (state.phase === "running") {
        runDetails.textContent = "Connection lost. Waiting for terminal run update.";
      }
    },
  });
}

function closeRunStream() {
  streamSubscription?.close();
  streamSubscription = null;
}

function renderPayloadSlot(
  container: HTMLElement,
  heading: string,
  payload: unknown,
  safety: CanonicalRunEvent["safety"]["tool_input"] | undefined,
) {
  container.replaceChildren();

  const title = document.createElement("p");
  title.className = "payload-heading";
  title.textContent = heading;
  container.append(title);

  if (payload === undefined) {
    const empty = document.createElement("p");
    empty.className = "payload-empty";
    empty.textContent = "No payload for this event.";
    container.append(empty);
    return;
  }

  const markers = document.createElement("div");
  markers.className = "payload-markers";

  if (safety?.redaction.active) {
    markers.append(
      createSignalBadge("Redaction", safety.redaction.paths, safety.redaction.reason),
    );
  }

  if (safety?.truncation.active) {
    markers.append(
      createSignalBadge(
        "Truncation",
        safety.truncation.paths,
        safety.truncation.omitted_bytes === undefined
          ? safety.truncation.reason
          : `${safety.truncation.omitted_bytes} bytes omitted`,
      ),
    );
  }

  if (markers.childElementCount > 0) {
    container.append(markers);
  }

  const pre = document.createElement("pre");
  pre.className = "payload-json";
  pre.textContent = JSON.stringify(payload, null, 2);
  container.append(pre);
}

function renderFinalAnswer(finalAnswer: string | undefined) {
  inspectorFinalAnswer.replaceChildren();

  const title = document.createElement("p");
  title.className = "payload-heading";
  title.textContent = "Final answer";
  inspectorFinalAnswer.append(title);

  const body = document.createElement("p");
  body.className = finalAnswer === undefined ? "payload-empty" : "payload-answer";
  body.textContent = finalAnswer ?? "No final answer on this event.";
  inspectorFinalAnswer.append(body);
}

function createSignalBadge(
  label: string,
  paths: string[],
  detail: string | undefined,
): HTMLElement {
  const badge = document.createElement("p");
  badge.className = "payload-signal";
  badge.textContent = `${label}: ${paths.length > 0 ? paths.join(", ") : "applied"}${
    detail ? ` (${detail})` : ""
  }`;
  return badge;
}

function requireElement<TElement extends HTMLElement>(id: string): TElement {
  const element = document.getElementById(id);
  if (!(element instanceof HTMLElement)) {
    throw new Error(`Missing required element: ${id}`);
  }

  return element as TElement;
}

function createPreviewEvents(): CanonicalRunEvent[] {
  return parseOrderedRunEventList([
    {
      run_id: "preview-run",
      event_seq: 0,
      event_type: "run_started",
      ts: "2026-03-17T12:00:00.000Z",
      tool_input: {
        prompt: "Compare retrieval SDKs and highlight reliability risks.",
      },
      safety: createEmptyRunEventSafety(),
    },
    {
      run_id: "preview-run",
      event_seq: 1,
      event_type: "tool_call_started",
      ts: "2026-03-17T12:00:01.000Z",
      tool_name: "web_search",
      tool_call_id: "tool-success",
      tool_input: {
        query: "retrieval sdk reliability release notes",
        headers: {
          authorization: "[Redacted]",
        },
      },
      safety: {
        ...createEmptyRunEventSafety(),
        tool_input: {
          redaction: {
            active: true,
            paths: ["headers.authorization"],
            reason: "secret",
          },
          truncation: {
            active: false,
            paths: [],
          },
        },
      },
    },
    {
      run_id: "preview-run",
      event_seq: 2,
      event_type: "tool_call_succeeded",
      ts: "2026-03-17T12:00:02.000Z",
      tool_name: "web_search",
      tool_call_id: "tool-success",
      tool_output: {
        results: [
          {
            title: "Retrieval SDK release notes",
            snippet: "Top result snippet kept.",
          },
          {
            title: "Long provider payload",
            snippet: "[Truncated]",
          },
        ],
      },
      safety: {
        ...createEmptyRunEventSafety(),
        tool_output: {
          redaction: {
            active: false,
            paths: [],
          },
          truncation: {
            active: true,
            paths: ["results.1.snippet"],
            omitted_bytes: 512,
          },
        },
      },
    },
    {
      run_id: "preview-run",
      event_seq: 3,
      event_type: "tool_call_failed",
      ts: "2026-03-17T12:00:03.000Z",
      tool_name: "web_crawl",
      tool_call_id: "tool-failure",
      tool_input: {
        url: "https://example.com/private",
        apiKey: "[Redacted]",
      },
      error_output: {
        code: "POLICY_DENIED",
        message: "Fetch blocked by policy.",
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
    },
    {
      run_id: "preview-run",
      event_seq: 4,
      event_type: "final_answer_generated",
      ts: "2026-03-17T12:00:04.000Z",
      final_answer: "Search succeeded, crawl failed safely, and the agent kept the error visible.",
      safety: createEmptyRunEventSafety(),
    },
  ]);
}
