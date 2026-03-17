import type { RunStartResponse } from "./api-client.js";

export type RunPhase = "idle" | "starting" | "running" | "failed";

export interface RunState {
  phase: RunPhase;
  prompt: string;
  activeRunId: string | null;
  error: string | null;
}

export type RunAction =
  | { type: "prompt_updated"; prompt: string }
  | { type: "run_requested" }
  | { type: "run_started"; response: RunStartResponse }
  | { type: "run_failed"; message: string };

export const initialRunState: RunState = {
  phase: "idle",
  prompt: "",
  activeRunId: null,
  error: null,
};

export function reduceRunState(state: RunState, action: RunAction): RunState {
  switch (action.type) {
    case "prompt_updated":
      return {
        ...state,
        prompt: action.prompt,
        ...(state.phase === "failed" ? { phase: "idle", error: null } : {}),
      };
    case "run_requested":
      if (state.phase === "starting" || state.phase === "running") {
        return state;
      }

      return {
        ...state,
        phase: "starting",
        activeRunId: null,
        error: null,
      };
    case "run_started":
      if (state.phase !== "starting") {
        return state;
      }

      return {
        ...state,
        phase: "running",
        activeRunId: action.response.runId,
        error: null,
      };
    case "run_failed":
      if (state.phase === "running") {
        return state;
      }

      return {
        ...state,
        phase: "failed",
        activeRunId: null,
        error: action.message,
      };
  }
}
