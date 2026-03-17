import { createRun } from "./api-client.js";
import { initialRunState, reduceRunState, type RunState } from "./state.js";

const promptInput = requireElement<HTMLInputElement>("prompt-input");
const promptError = requireElement<HTMLElement>("prompt-error");
const runForm = requireElement<HTMLFormElement>("run-form");
const runButton = requireElement<HTMLButtonElement>("run-submit");
const runStatus = requireElement<HTMLElement>("run-status");
const runDetails = requireElement<HTMLElement>("run-details");

let state = initialRunState;

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

  dispatch({ type: "run_requested" });

  const result = await createRun({ prompt });
  if (result.ok) {
    dispatch({
      type: "run_started",
      response: result.data,
    });
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
}

function statusLabel(currentState: RunState): string {
  switch (currentState.phase) {
    case "idle":
      return "Idle";
    case "starting":
      return "Starting";
    case "running":
      return "Running";
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
      return currentState.activeRunId === null
        ? "Run active."
        : `Run ${currentState.activeRunId} is active.`;
    case "failed":
      return currentState.error ?? "Run could not be started.";
  }
}

function requireElement<TElement extends HTMLElement>(id: string): TElement {
  const element = document.getElementById(id);
  if (!(element instanceof HTMLElement)) {
    throw new Error(`Missing required element: ${id}`);
  }

  return element as TElement;
}
