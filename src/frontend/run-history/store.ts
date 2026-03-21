import {
  parseOrderedRunEventList,
  parseRunEvent,
  type CanonicalRunEvent,
} from "../contracts.js";

export interface RunHistoryStoreLimits {
  maxRuns: number;
  maxEventsPerRun: number;
  maxPayloadBytes: number;
}

export interface RunHistoryEventTruncation {
  eventSeq: number;
  eventType: CanonicalRunEvent["event_type"];
  fields: Array<RunHistoryPayloadField>;
  omittedBytes: number;
}

export interface RunHistoryRetentionMetadata {
  maxRuns: number;
  maxEventsPerRun: number;
  maxPayloadBytes: number;
  duplicateEventsIgnored: number;
  outOfOrderEventsRejected: number;
  eventsDropped: number;
  payloadTruncations: RunHistoryEventTruncation[];
}

export interface RunHistoryRunSnapshot {
  runId: string;
  finalAnswer: string | null;
  events: CanonicalRunEvent[];
  createdAt: string;
  updatedAt: string;
  retention: RunHistoryRetentionMetadata;
}

export interface RunHistoryRunSummary {
  runId: string;
  finalAnswer: string | null;
  eventCount: number;
  createdAt: string;
  updatedAt: string;
  latestEventSeq: number | null;
  retention: RunHistoryRetentionMetadata;
}

export interface RunHistoryIngestResult {
  status: "appended" | "ignored_duplicate" | "rejected_out_of_order";
  runId: string;
  eventSeq: number;
}

interface InternalRunRecord {
  runId: string;
  finalAnswer: string | null;
  events: CanonicalRunEvent[];
  createdAtMs: number;
  updatedAtMs: number;
  retention: RunHistoryRetentionMetadata;
}

type RunHistoryPayloadField =
  | "tool_input"
  | "tool_output"
  | "error_output"
  | "final_answer";

const DEFAULT_LIMITS: RunHistoryStoreLimits = {
  maxRuns: 25,
  maxEventsPerRun: 100,
  maxPayloadBytes: 32_768,
};
const MAX_RETENTION_TRUNCATIONS = 100;

const TRUNCATED_PAYLOAD_SENTINEL = "[Truncated run history payload]";
const TRUNCATED_FINAL_ANSWER_SENTINEL = "[Truncated run history answer]";
const TRUNCATED_PAYLOAD_PATH = "$";
const RUN_HISTORY_PAYLOAD_FIELDS: readonly RunHistoryPayloadField[] = [
  "tool_input",
  "tool_output",
  "error_output",
  "final_answer",
];

export function createRunHistoryStore(
  limits: Partial<RunHistoryStoreLimits> = {},
) {
  const resolvedLimits = resolveLimits(limits);
  const runs = new Map<string, InternalRunRecord>();

  return {
    ingest(eventLike: unknown): RunHistoryIngestResult {
      const incomingEvent = parseRunEvent(eventLike);
      const run = getOrCreateRun(runs, incomingEvent.run_id, resolvedLimits);
      const existingEvent = run.events.find(
        (event) => event.event_seq === incomingEvent.event_seq,
      );

      if (existingEvent !== undefined) {
        run.retention.duplicateEventsIgnored += 1;
        run.updatedAtMs = Date.now();

        return {
          status: "ignored_duplicate",
          runId: run.runId,
          eventSeq: incomingEvent.event_seq,
        };
      }

      const highestEventSeq = run.events.at(-1)?.event_seq ?? -1;
      if (incomingEvent.event_seq < highestEventSeq) {
        run.retention.outOfOrderEventsRejected += 1;
        run.updatedAtMs = Date.now();

        return {
          status: "rejected_out_of_order",
          runId: run.runId,
          eventSeq: incomingEvent.event_seq,
        };
      }

      const { event, truncation } = truncateEventForStorage(
        incomingEvent,
        resolvedLimits.maxPayloadBytes,
      );

      run.events.push(event);
      run.events = parseOrderedRunEventList(run.events);
      run.finalAnswer = resolveRunFinalAnswer(run.finalAnswer, event);
      run.updatedAtMs = Date.now();

      if (truncation !== null) {
        run.retention.payloadTruncations.push(truncation);
        trimRetentionTruncations(run.retention);
      }

      while (run.events.length > resolvedLimits.maxEventsPerRun) {
        run.events.shift();
        run.retention.eventsDropped += 1;
      }

      evictExcessRuns(runs, resolvedLimits.maxRuns);

      return {
        status: "appended",
        runId: run.runId,
        eventSeq: event.event_seq,
      };
    },

    getRun(runId: string): RunHistoryRunSnapshot | null {
      const run = runs.get(runId);
      return run === undefined ? null : toRunSnapshot(run);
    },

    listRuns(): RunHistoryRunSummary[] {
      return [...runs.values()]
        .sort(compareRunsByRecency)
        .map((run) => ({
          runId: run.runId,
          finalAnswer: run.finalAnswer,
          eventCount: run.events.length,
          createdAt: new Date(run.createdAtMs).toISOString(),
          updatedAt: new Date(run.updatedAtMs).toISOString(),
          latestEventSeq: run.events.at(-1)?.event_seq ?? null,
          retention: cloneRetention(run.retention),
        }));
    },

    clear() {
      runs.clear();
    },
  };
}

function resolveLimits(
  limits: Partial<RunHistoryStoreLimits>,
): RunHistoryStoreLimits {
  return {
    maxRuns: validateLimit(limits.maxRuns ?? DEFAULT_LIMITS.maxRuns, "maxRuns"),
    maxEventsPerRun: validateLimit(
      limits.maxEventsPerRun ?? DEFAULT_LIMITS.maxEventsPerRun,
      "maxEventsPerRun",
    ),
    maxPayloadBytes: validateLimit(
      limits.maxPayloadBytes ?? DEFAULT_LIMITS.maxPayloadBytes,
      "maxPayloadBytes",
    ),
  };
}

function validateLimit(value: number, name: string): number {
  if (!Number.isInteger(value) || value < 1) {
    throw new Error(`${name} must be a positive integer.`);
  }

  return value;
}

function getOrCreateRun(
  runs: Map<string, InternalRunRecord>,
  runId: string,
  limits: RunHistoryStoreLimits,
): InternalRunRecord {
  const existing = runs.get(runId);
  if (existing !== undefined) {
    return existing;
  }

  const now = Date.now();
  const created: InternalRunRecord = {
    runId,
    finalAnswer: null,
    events: [],
    createdAtMs: now,
    updatedAtMs: now,
    retention: {
      maxRuns: limits.maxRuns,
      maxEventsPerRun: limits.maxEventsPerRun,
      maxPayloadBytes: limits.maxPayloadBytes,
      duplicateEventsIgnored: 0,
      outOfOrderEventsRejected: 0,
      eventsDropped: 0,
      payloadTruncations: [],
    },
  };

  runs.set(runId, created);
  return created;
}

function evictExcessRuns(runs: Map<string, InternalRunRecord>, maxRuns: number) {
  while (runs.size > maxRuns) {
    const oldestRun = [...runs.values()].sort(compareRunsByAge)[0];

    if (oldestRun === undefined) {
      return;
    }

    runs.delete(oldestRun.runId);
  }
}

function compareRunsByRecency(
  left: InternalRunRecord,
  right: InternalRunRecord,
): number {
  return compareRunsByAge(right, left);
}

function compareRunsByAge(
  left: InternalRunRecord,
  right: InternalRunRecord,
): number {
  if (left.updatedAtMs !== right.updatedAtMs) {
    return left.updatedAtMs - right.updatedAtMs;
  }

  if (left.createdAtMs !== right.createdAtMs) {
    return left.createdAtMs - right.createdAtMs;
  }

  return left.runId.localeCompare(right.runId);
}

function truncateEventForStorage(
  event: CanonicalRunEvent,
  maxPayloadBytes: number,
): {
  event: CanonicalRunEvent;
  truncation: RunHistoryEventTruncation | null;
} {
  let nextEvent: CanonicalRunEvent = structuredClone(event);
  let totalBytes = countEventPayloadBytes(nextEvent);

  if (totalBytes <= maxPayloadBytes) {
    return {
      event: nextEvent,
      truncation: null,
    };
  }

  const fields: RunHistoryPayloadField[] = [];

  for (const field of RUN_HISTORY_PAYLOAD_FIELDS) {
    const fieldValue = nextEvent[field];
    if (fieldValue === undefined) {
      continue;
    }

    const beforeBytes = countSerializedBytes(fieldValue);
    if (field === "final_answer") {
      nextEvent = {
        ...nextEvent,
        final_answer: truncateFinalAnswer(
          typeof fieldValue === "string" ? fieldValue : String(fieldValue),
        ),
      };
    } else {
      nextEvent = truncateEventPayloadField(nextEvent, field);
    }

    const afterValue = nextEvent[field];
    const afterBytes =
      afterValue === undefined ? 0 : countSerializedBytes(afterValue);

    if (afterBytes < beforeBytes) {
      fields.push(field);
    }

    totalBytes = countEventPayloadBytes(nextEvent);
    if (totalBytes <= maxPayloadBytes) {
      break;
    }
  }

  if (totalBytes > maxPayloadBytes && nextEvent.final_answer !== undefined) {
    const beforeBytes = countSerializedBytes(nextEvent.final_answer);
    nextEvent = {
      ...nextEvent,
      final_answer: TRUNCATED_FINAL_ANSWER_SENTINEL,
    };

    if (countSerializedBytes(nextEvent.final_answer) < beforeBytes) {
      fields.push("final_answer");
    }
  }

  return {
    event: nextEvent,
    truncation:
      fields.length === 0
        ? null
        : {
            eventSeq: event.event_seq,
            eventType: event.event_type,
            fields,
            omittedBytes: Math.max(
              0,
              countEventPayloadBytes(event) - countEventPayloadBytes(nextEvent),
            ),
          },
  };
}

function truncateEventPayloadField(
  event: CanonicalRunEvent,
  field: Exclude<RunHistoryPayloadField, "final_answer">,
): CanonicalRunEvent {
  const nextPaths = new Set(event.safety[field].truncation.paths);
  nextPaths.add(TRUNCATED_PAYLOAD_PATH);

  return {
    ...event,
    [field]: TRUNCATED_PAYLOAD_SENTINEL,
    safety: {
      ...event.safety,
      [field]: {
        ...event.safety[field],
        truncation: {
          active: true,
          paths: [...nextPaths],
          reason: event.safety[field].truncation.reason ?? "payload_limit",
          omitted_bytes:
            countSerializedBytes(event[field] ?? null) -
            countSerializedBytes(TRUNCATED_PAYLOAD_SENTINEL),
        },
      },
    },
  };
}

function truncateFinalAnswer(answer: string): string {
  const head = answer.slice(0, 120).trimEnd();
  return head.length === 0
    ? TRUNCATED_FINAL_ANSWER_SENTINEL
    : `${head} ${TRUNCATED_FINAL_ANSWER_SENTINEL}`;
}

function countEventPayloadBytes(event: CanonicalRunEvent): number {
  let totalBytes = 0;

  for (const field of RUN_HISTORY_PAYLOAD_FIELDS) {
    const value = event[field];
    totalBytes += value === undefined ? 0 : countSerializedBytes(value);
  }

  return totalBytes;
}

function countSerializedBytes(value: unknown): number {
  return Buffer.byteLength(JSON.stringify(value), "utf8");
}

function resolveRunFinalAnswer(
  currentFinalAnswer: string | null,
  event: CanonicalRunEvent,
): string | null {
  return event.final_answer ?? currentFinalAnswer;
}

function toRunSnapshot(run: InternalRunRecord): RunHistoryRunSnapshot {
  return {
    runId: run.runId,
    finalAnswer: run.finalAnswer,
    events: structuredClone(run.events),
    createdAt: new Date(run.createdAtMs).toISOString(),
    updatedAt: new Date(run.updatedAtMs).toISOString(),
    retention: cloneRetention(run.retention),
  };
}

function cloneRetention(
  retention: RunHistoryRetentionMetadata,
): RunHistoryRetentionMetadata {
  return {
    ...retention,
    payloadTruncations: retention.payloadTruncations.map((entry) => ({
      ...entry,
      fields: [...entry.fields],
    })),
  };
}

function trimRetentionTruncations(retention: RunHistoryRetentionMetadata) {
  while (retention.payloadTruncations.length > MAX_RETENTION_TRUNCATIONS) {
    retention.payloadTruncations.shift();
  }
}
