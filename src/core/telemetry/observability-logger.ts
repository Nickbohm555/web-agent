import { randomUUID } from "node:crypto";
import pino from "pino";
import {
  createEmptyRunEventSafety,
  parseRunEvent,
  type CanonicalRunEvent,
  type CanonicalRunEventJson,
  type CanonicalRunEventRetrievalAction,
  type CanonicalRunEventPayloadSafety,
  type CanonicalRunEventToolName,
} from "../../frontend/contracts.js";
import { nextRunEventSequence, requireRunContext } from "./run-context.js";

const REDACTION_SENTINEL = "[Redacted]";
const TRUNCATION_SENTINEL = "[Truncated]";
const TRUNCATED_PAYLOAD_SENTINEL = "[Truncated observability payload]";
const MAX_STRING_LENGTH = 256;
const MAX_ARRAY_ITEMS = 20;
const MAX_OBJECT_ENTRIES = 20;
const MAX_PAYLOAD_BYTES = 4_096;
const SENSITIVE_FIELD_NAMES = new Set([
  "apiKey",
  "authorization",
  "password",
  "secret",
  "token",
]);

const logger = pino({
  level: process.env.LOG_LEVEL ?? "info",
  base: null,
  timestamp: false,
});

interface ObservabilityToolEventInput {
  toolName: CanonicalRunEventToolName;
  toolCallId?: string;
}

interface ToolCallStartedInput extends ObservabilityToolEventInput {
  toolInput: unknown;
}

interface ToolCallSucceededInput extends ObservabilityToolEventInput {
  toolOutput: unknown;
}

interface ToolCallFailedInput extends ObservabilityToolEventInput {
  toolInput?: unknown;
  errorOutput: unknown;
}

export function createToolCallId(): string {
  return randomUUID();
}

export function emitToolCallStarted(
  input: ToolCallStartedInput,
): CanonicalRunEvent {
  return emitRunEvent({
    event_type: "tool_call_started",
    tool_name: input.toolName,
    tool_call_id: input.toolCallId ?? createToolCallId(),
    tool_input: input.toolInput,
  });
}

export function emitToolCallSucceeded(
  input: ToolCallSucceededInput,
): CanonicalRunEvent {
  return emitRunEvent({
    event_type: "tool_call_succeeded",
    tool_name: input.toolName,
    tool_call_id: input.toolCallId ?? createToolCallId(),
    tool_output: input.toolOutput,
  });
}

export function emitToolCallFailed(
  input: ToolCallFailedInput,
): CanonicalRunEvent {
  return emitRunEvent({
    event_type: "tool_call_failed",
    tool_name: input.toolName,
    tool_call_id: input.toolCallId ?? createToolCallId(),
    ...(input.toolInput !== undefined ? { tool_input: input.toolInput } : {}),
    error_output: input.errorOutput,
  });
}

function emitRunEvent(
  input: Pick<
    CanonicalRunEvent,
    "event_type" | "tool_name" | "tool_call_id"
  > & {
    tool_input?: unknown;
    tool_output?: unknown;
    error_output?: unknown;
  },
): CanonicalRunEvent {
  const { run_id } = requireRunContext();
  const safety = createEmptyRunEventSafety();
  const toolInput = sanitizePayload(input.tool_input);
  const toolOutput = sanitizePayload(input.tool_output);
  const errorOutput = sanitizePayload(input.error_output);
  const retrievalAction = deriveRetrievalAction({
    toolName: input.tool_name,
    toolCallId: input.tool_call_id,
    toolInput: input.tool_input,
    toolOutput: input.tool_output,
    errorOutput: input.error_output,
  });

  const event = parseRunEvent({
    run_id,
    event_seq: nextRunEventSequence(),
    event_type: input.event_type,
    ts: new Date().toISOString(),
    ...(input.tool_name !== undefined ? { tool_name: input.tool_name } : {}),
    ...(input.tool_call_id !== undefined
      ? { tool_call_id: input.tool_call_id }
      : {}),
    ...(retrievalAction !== undefined
      ? { retrieval_action: retrievalAction }
      : {}),
    ...(toolInput.payload !== undefined
      ? { tool_input: toolInput.payload }
      : {}),
    ...(toolOutput.payload !== undefined
      ? { tool_output: toolOutput.payload }
      : {}),
    ...(errorOutput.payload !== undefined
      ? { error_output: errorOutput.payload }
      : {}),
    safety: {
      ...safety,
      tool_input: toolInput.safety,
      tool_output: toolOutput.safety,
      error_output: errorOutput.safety,
    },
  });

  logger.info(event);
  return event;
}

function deriveRetrievalAction(input: {
  toolName: CanonicalRunEventToolName | undefined;
  toolCallId: string | undefined;
  toolInput: unknown;
  toolOutput: unknown;
  errorOutput: unknown;
}): CanonicalRunEventRetrievalAction | undefined {
  if (input.toolName === "web_search") {
    const query =
      readStringField(input.toolInput, "query") ??
      readStringField(input.toolOutput, "query");
    if (query === undefined) {
      return undefined;
    }
    const resultCount = readSearchResultCount(input.toolOutput);

    return {
      action_id: input.toolCallId ?? createToolCallId(),
      action_type: "search",
      query,
      ...(resultCount !== undefined ? { result_count: resultCount } : {}),
    };
  }

  if (input.toolName === "open_url") {
    const url =
      readUrlField(input.toolInput, "url") ??
      readUrlField(input.toolOutput, "final_url") ??
      readUrlField(input.toolOutput, "url");
    if (url === undefined) {
      return undefined;
    }

    return {
      action_id: input.toolCallId ?? createToolCallId(),
      action_type: "open_page",
      url,
    };
  }

  return undefined;
}

function readSearchResultCount(value: unknown): number | undefined {
  const metadata = readObjectField(value, "metadata");
  const explicitCount = readNumberField(metadata, "result_count");
  if (explicitCount !== undefined) {
    return explicitCount;
  }

  const results = readArrayField(value, "results");
  return results?.length;
}

function readStringField(value: unknown, field: string): string | undefined {
  const record = asRecord(value);
  const candidate = record?.[field];
  return typeof candidate === "string" && candidate.trim().length > 0
    ? candidate
    : undefined;
}

function readNumberField(value: unknown, field: string): number | undefined {
  const record = asRecord(value);
  const candidate = record?.[field];
  return typeof candidate === "number" && Number.isFinite(candidate)
    ? candidate
    : undefined;
}

function readUrlField(value: unknown, field: string): string | undefined {
  const candidate = readStringField(value, field);
  if (candidate === undefined) {
    return undefined;
  }

  try {
    return new URL(candidate).toString();
  } catch {
    return undefined;
  }
}

function readObjectField(
  value: unknown,
  field: string,
): Record<string, unknown> | undefined {
  const record = asRecord(value);
  return asRecord(record?.[field]);
}

function readArrayField(value: unknown, field: string): unknown[] | undefined {
  const record = asRecord(value);
  const candidate = record?.[field];
  return Array.isArray(candidate) ? candidate : undefined;
}

function asRecord(value: unknown): Record<string, unknown> | undefined {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : undefined;
}

function sanitizePayload(input: unknown): {
  payload?: CanonicalRunEventJson;
  safety: CanonicalRunEventPayloadSafety;
} {
  const redactionPaths: string[] = [];
  const truncationPaths: string[] = [];
  let omittedBytes = 0;

  const payload = sanitizeValue(input, "", {
    redactionPaths,
    truncationPaths,
    onTruncate(bytes) {
      omittedBytes += bytes;
    },
  });

  const boundedPayload = boundSerializedPayloadSize(
    payload,
    truncationPaths,
    (bytes) => {
      omittedBytes += bytes;
    },
  );

  return {
    ...(boundedPayload !== undefined ? { payload: boundedPayload } : {}),
    safety: {
      redaction: {
        active: redactionPaths.length > 0,
        paths: redactionPaths,
        ...(redactionPaths.length > 0 ? { reason: "secret" } : {}),
      },
      truncation: {
        active: truncationPaths.length > 0,
        paths: truncationPaths,
        ...(truncationPaths.length > 0 ? { omitted_bytes: omittedBytes } : {}),
      },
    },
  };
}

function sanitizeValue(
  value: unknown,
  path: string,
  state: {
    redactionPaths: string[];
    truncationPaths: string[];
    onTruncate: (bytes: number) => void;
  },
): CanonicalRunEventJson | undefined {
  if (value === undefined) {
    return undefined;
  }

  if (value === null || typeof value === "boolean" || typeof value === "number") {
    return value;
  }

  if (typeof value === "string") {
    return truncateString(value, path, state);
  }

  if (typeof value === "bigint") {
    return value.toString();
  }

  if (value instanceof Date) {
    return value.toISOString();
  }

  if (value instanceof Error) {
    return sanitizeValue(
      {
        name: value.name,
        message: value.message,
        ...(value.stack ? { stack: value.stack } : {}),
      },
      path,
      state,
    );
  }

  if (Array.isArray(value)) {
    const result = value
      .slice(0, MAX_ARRAY_ITEMS)
      .map((entry, index) =>
        sanitizeValue(entry, appendPath(path, String(index)), state) ?? null,
      );

    if (value.length > MAX_ARRAY_ITEMS) {
      const truncatedPath = appendPath(path, String(MAX_ARRAY_ITEMS));
      state.truncationPaths.push(truncatedPath);
      state.onTruncate(value.length - MAX_ARRAY_ITEMS);
      result.push(TRUNCATION_SENTINEL);
    }

    return result;
  }

  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>);
    const result: Record<string, CanonicalRunEventJson> = {};

    for (const [index, [key, entry]] of entries.entries()) {
      const entryPath = appendPath(path, key);

      if (SENSITIVE_FIELD_NAMES.has(key)) {
        state.redactionPaths.push(entryPath);
        result[key] = REDACTION_SENTINEL;
        continue;
      }

      if (index >= MAX_OBJECT_ENTRIES) {
        state.truncationPaths.push(entryPath);
        state.onTruncate(entries.length - MAX_OBJECT_ENTRIES);
        result[key] = TRUNCATION_SENTINEL;
        continue;
      }

      const sanitized = sanitizeValue(entry, entryPath, state);
      if (sanitized !== undefined) {
        result[key] = sanitized;
      }
    }

    return result;
  }

  return String(value);
}

function truncateString(
  value: string,
  path: string,
  state: {
    redactionPaths: string[];
    truncationPaths: string[];
    onTruncate: (bytes: number) => void;
  },
): string {
  if (value.length <= MAX_STRING_LENGTH) {
    return value;
  }

  if (path.length > 0) {
    state.truncationPaths.push(path);
  }
  state.onTruncate(value.length - MAX_STRING_LENGTH);
  return `${value.slice(0, MAX_STRING_LENGTH)}${TRUNCATION_SENTINEL}`;
}

function appendPath(prefix: string, segment: string): string {
  return prefix.length === 0 ? segment : `${prefix}.${segment}`;
}

function boundSerializedPayloadSize(
  payload: CanonicalRunEventJson | undefined,
  truncationPaths: string[],
  onTruncate: (bytes: number) => void,
): CanonicalRunEventJson | undefined {
  if (payload === undefined) {
    return undefined;
  }

  const serialized = JSON.stringify(payload);
  const payloadBytes = Buffer.byteLength(serialized, "utf8");
  if (payloadBytes <= MAX_PAYLOAD_BYTES) {
    return payload;
  }

  truncationPaths.push("$");
  onTruncate(payloadBytes - MAX_PAYLOAD_BYTES);
  return TRUNCATED_PAYLOAD_SENTINEL;
}
