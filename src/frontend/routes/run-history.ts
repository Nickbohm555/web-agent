import { Router } from "express";
import {
  RunHistoryListResponseSchema,
  RunHistoryNotFoundErrorSchema,
  RunHistoryRunSnapshotSchema,
} from "../contracts.js";
import type {
  RunHistoryRunSnapshot,
  RunHistoryRunSummary,
} from "../run-history/store.js";

interface RunHistoryStoreLike {
  getRun(runId: string): RunHistoryRunSnapshot | null;
  listRuns(): RunHistoryRunSummary[];
}

export function createRunHistoryRouter(): Router {
  const router = Router();

  router.get("/history", (req, res) => {
    const store = getRunHistoryStore(req.app.locals.runHistoryStore);
    const response = RunHistoryListResponseSchema.parse({
      runs: store?.listRuns() ?? [],
    });

    res.status(200).json(response);
  });

  router.get("/:runId/history", (req, res) => {
    const store = getRunHistoryStore(req.app.locals.runHistoryStore);
    const snapshot = store?.getRun(req.params.runId) ?? null;

    if (snapshot === null) {
      res.status(404).json(
        RunHistoryNotFoundErrorSchema.parse({
          error: {
            code: "RUN_HISTORY_NOT_FOUND",
            message: `Run history for '${req.params.runId}' was not found.`,
          },
        }),
      );
      return;
    }

    res.status(200).json(RunHistoryRunSnapshotSchema.parse(snapshot));
  });

  return router;
}

function getRunHistoryStore(input: unknown): RunHistoryStoreLike | null {
  if (
    typeof input !== "object" ||
    input === null ||
    typeof (input as RunHistoryStoreLike).getRun !== "function" ||
    typeof (input as RunHistoryStoreLike).listRuns !== "function"
  ) {
    return null;
  }

  return input as RunHistoryStoreLike;
}
