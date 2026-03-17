import {
  createRun,
  subscribeToRunEvents,
  type RunStreamSubscription,
} from "./api-client.js";
import { initialRunState, reduceRunState, type RunState } from "./state.js";
import { toTimelineRows } from "./timeline.js";

const promptInput = requireElement<HTMLInputElement>("prompt-input");
const promptError = requireElement<HTMLElement>("prompt-error");
const runForm = requireElement<HTMLFormElement>("run-form");
const runButton = requireElement<HTMLButtonElement>("run-submit");
const runStatus = requireElement<HTMLElement>("run-status");
const runDetails = requireElement<HTMLElement>("run-details");
const timelineEmpty = requireElement<HTMLElement>("timeline-empty");
const timelineList = requireElement<HTMLElement>("timeline-list");

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
  switch (currentState.phase) {
    case "idle":
      return "Enter a prompt to start one run.";
    case "starting":
      return "Creating run...";
    case "running":
      if (currentState.toolCalls.length === 0) {
        return currentState.activeRunId === null
          ? "Run active."
          : `Run ${currentState.activeRunId} is active. Waiting for tool activity.`;
      }

      return currentState.activeRunId === null
        ? "Run active."
        : `Run ${currentState.activeRunId} is active. Timeline is live.`;
    case "completed":
      return currentState.finalAnswer ?? "Run completed.";
    case "failed":
      return currentState.error ?? "Run could not be started.";
  }
}

function renderTimeline() {
  const rows = toTimelineRows(state.toolCalls, { nowMs: Date.now() });
  timelineEmpty.hidden = rows.length > 0;

  timelineList.replaceChildren(
    ...rows.map((row) => {
      const item = document.createElement("li");
      item.className = "timeline-row";
      item.dataset.status = row.status;

      const toolName = document.createElement("p");
      toolName.className = "timeline-tool";
      toolName.textContent = row.toolName;

      const status = document.createElement("span");
      status.className = "timeline-badge";
      status.dataset.status = row.status;
      status.textContent = row.statusLabel;

      const duration = document.createElement("p");
      duration.className = "timeline-duration";
      duration.textContent = row.durationLabel;

      item.append(toolName, status, duration);
      return item;
    }),
  );
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

function requireElement<TElement extends HTMLElement>(id: string): TElement {
  const element = document.getElementById(id);
  if (!(element instanceof HTMLElement)) {
    throw new Error(`Missing required element: ${id}`);
  }

  return element as TElement;
}
