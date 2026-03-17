import { randomUUID } from "node:crypto";
import pino from "pino";
import {
  createEmptyRunEventSafety,
  parseRunEvent,
  type CanonicalRunEvent,
  type CanonicalRunEventJson,
  type CanonicalRunEventPayloadSafety,
  type CanonicalRunEventToolName,
} from "../../frontend/contracts.js";
import { nextRunEventSequence, requireRunContext } from "./run-context.js";

const REDACTION_SENTINEL = "[Redacted]";
const TRUNCATION_SENTINEL = "[Truncated]";
const MAX_STRING_LENGTH = 256;
const MAX_ARRAY_ITEMS = 20;
const MAX_OBJECT_ENTRIES = 20;
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

  const event = parseRunEvent({
    run_id,
    event_seq: nextRunEventSequence(),
    event_type: input.event_type,
    ts: new Date().toISOString(),
    ...(input.tool_name !== undefined ? { tool_name: input.tool_name } : {}),
    ...(input.tool_call_id !== undefined
      ? { tool_call_id: input.tool_call_id }
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

  return {
    ...(payload !== undefined ? { payload } : {}),
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
