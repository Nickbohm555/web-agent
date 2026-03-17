import { AsyncLocalStorage } from "node:async_hooks";
import { randomUUID } from "node:crypto";

interface RunContextStore {
  runId: string;
  nextEventSeq: number;
}

const runContextStorage = new AsyncLocalStorage<RunContextStore>();

export interface RunContextValue {
  run_id: string;
  event_seq: number;
}

export interface RunContextOptions {
  runId?: string;
}

export function withRunContext<T>(
  callback: () => T,
  options: RunContextOptions = {},
): T {
  const runId = options.runId?.trim() || randomUUID();

  return runContextStorage.run(
    {
      runId,
      nextEventSeq: 0,
    },
    callback,
  );
}

export function getRunContext(): RunContextValue | null {
  const store = runContextStorage.getStore();
  if (store === undefined) {
    return null;
  }

  return {
    run_id: store.runId,
    event_seq: store.nextEventSeq,
  };
}

export function requireRunContext(): RunContextValue {
  const context = getRunContext();
  if (context === null) {
    throw new Error("Run context is unavailable.");
  }

  return context;
}

export function nextRunEventSequence(): number {
  const store = runContextStorage.getStore();
  if (store === undefined) {
    throw new Error("Run context is unavailable.");
  }

  const eventSeq = store.nextEventSeq;
  store.nextEventSeq += 1;
  return eventSeq;
}
