import { ZodError, z } from "zod";
import { measureDurationMs, startCallTimer } from "../core/telemetry/call-meta.js";
import {
  createEmptyRunEventSafety,
  createRunEventKey,
  parseOrderedRunEventList,
  parseRunEvent,
  parseRunEventList,
  RunEventListSchema,
  RunEventSchema,
  RunEventTypeSchema,
  type RunEvent,
  type RunEventJson,
  type RunEventPayloadSafety,
  type RunEventPayloadSignal,
  type RunProgress,
  type RunProgressStage,
  type RunEventSafety,
  type RunEventRetrievalAction as CanonicalRunEventRetrievalActionType,
  type RunEventRetrievalActionType as CanonicalRunEventRetrievalActionKindType,
  type RunEventToolName as CanonicalRunEventToolNameType,
  type RunEventType,
} from "./contracts/run-events.js";
import {
  isSdkError,
  type SdkError,
  type SdkErrorKind,
} from "../core/errors/sdk-error.js";
import {
  type FetchSafetyError,
} from "../core/errors/fetch-safety-error.js";
import {
  FetchRequestSchema,
  FetchResponseSchema,
  type FetchOptions,
} from "../sdk/contracts/fetch.js";
import {
  SearchRequestSchema,
  SearchResponseSchema,
  type SearchOptions,
} from "../sdk/contracts/search.js";
import {
  FetchControlsInputSchema,
  mergeRunPolicyIntoFetchInput,
  mergeRunPolicyIntoSearchInput,
  resolveRunRetrievalPolicy,
  RunRetrievalPolicyInputSchema,
  SearchControlsInputSchema,
} from "../core/policy/retrieval-controls.js";

export const FrontendOperationSchema = z.enum(["search", "fetch", "run_start"]);
export const RunModeSchema = z.enum(["quick", "agentic", "deep_research"]);

export const FrontendErrorCodeSchema = z.enum([
  "VALIDATION_ERROR",
  "RATE_LIMITED",
  "TIMEOUT",
  "NETWORK_ERROR",
  "PROVIDER_UNAVAILABLE",
  "INVALID_REQUEST",
  "POLICY_DENIED",
  "CONTENT_UNAVAILABLE",
  "INTERNAL_ERROR",
]);

export const FrontendValidationErrorDetailsSchema = z
  .object({
    formErrors: z.array(z.string()),
    fieldErrors: z.record(z.string(), z.array(z.string())),
  })
  .strict();

export const FrontendSdkErrorDetailsSchema = z
  .object({
    kind: z.string(),
    retryable: z.boolean(),
    statusCode: z.number().int().positive().optional(),
    retryAfterMs: z.number().nonnegative().optional(),
    stage: z.string().optional(),
    reason: z.string().optional(),
    fallbackReason: z.string().nullable().optional(),
    meta: z.unknown().optional(),
    metadata: z.unknown().optional(),
  })
  .strict();

export const FrontendErrorSchema = z
  .object({
    code: FrontendErrorCodeSchema,
    message: z.string().min(1),
    details: z
      .union([
        FrontendValidationErrorDetailsSchema,
        FrontendSdkErrorDetailsSchema,
      ])
      .optional(),
  })
  .strict();

const NormalizedSearchApiRequestSchema = z
  .object({
    query: z.string().min(1),
    options: z.object({
      maxResults: z.number().int().min(1).max(10),
      timeoutMs: z.number().int().min(1000).max(10000),
      country: z.string().length(2),
      language: z.string().length(2),
      freshness: z.enum(["day", "week", "month", "year", "any"]),
      domainScope: z.object({
        includeDomains: z.array(z.string()),
        excludeDomains: z.array(z.string()),
      }).strict(),
    }).strict(),
  })
  .strict();

const NormalizedFetchApiRequestSchema = z
  .object({
    url: z.string().url(),
    options: z.object({
      timeoutMs: z.number().int().min(1000).max(10000),
      maxAgeMs: z.number().int().min(0).max(86_400_000),
      fresh: z.boolean(),
    }).strict(),
  })
  .strict();

const SearchApiSuccessEnvelopeSchema = z
  .object({
    ok: z.literal(true),
    operation: z.literal("search"),
    durationMs: z.number().nonnegative(),
    request: NormalizedSearchApiRequestSchema,
    data: SearchResponseSchema,
  })
  .strict();

const SearchApiErrorEnvelopeSchema = z
  .object({
    ok: z.literal(false),
    operation: z.literal("search"),
    durationMs: z.number().nonnegative(),
    request: NormalizedSearchApiRequestSchema.nullable(),
    error: FrontendErrorSchema,
  })
  .strict();

const FetchApiSuccessEnvelopeSchema = z
  .object({
    ok: z.literal(true),
    operation: z.literal("fetch"),
    durationMs: z.number().nonnegative(),
    request: NormalizedFetchApiRequestSchema,
    data: FetchResponseSchema,
  })
  .strict();

const FetchApiErrorEnvelopeSchema = z
  .object({
    ok: z.literal(false),
    operation: z.literal("fetch"),
    durationMs: z.number().nonnegative(),
    request: NormalizedFetchApiRequestSchema.nullable(),
    error: FrontendErrorSchema,
  })
  .strict();

const NormalizedRunRetrievalPolicySchema = z
  .object({
    search: z.object({
      country: z.string().length(2),
      language: z.string().length(2),
      freshness: z.enum(["day", "week", "month", "year", "any"]),
      domainScope: z.object({
        includeDomains: z.array(z.string()),
        excludeDomains: z.array(z.string()),
      }).strict(),
    }).strict(),
    fetch: z.object({
      maxAgeMs: z.number().int().min(0).max(86_400_000),
      fresh: z.boolean(),
    }).strict(),
  })
  .strict();

export const RunStartRequestSchema = z
  .object({
    prompt: z.string().trim().min(1),
    mode: RunModeSchema,
    retrievalPolicy: RunRetrievalPolicyInputSchema.optional(),
  })
  .strict()
  .transform((input) => ({
    prompt: input.prompt,
    mode: input.mode,
    retrievalPolicy: resolveRunRetrievalPolicy(input.retrievalPolicy, input.prompt),
  }));

export const RunStartStatusSchema = z.enum(["queued", "running"]);

export const RunStartResponseSchema = z
  .object({
    runId: z.uuid(),
    status: RunStartStatusSchema,
  })
  .strict();

export const RunSourceSchema = z
  .object({
    source_id: z.string().trim().min(1),
    title: z.string().trim().min(1),
    url: z.string().url(),
    snippet: z.string(),
  })
  .strict();

export const StructuredAnswerCitationSchema = z
  .object({
    source_id: z.string().trim().min(1),
    title: z.string().trim().min(1),
    url: z.string().url(),
    start_index: z.number().int().nonnegative(),
    end_index: z.number().int().positive(),
  })
  .strict()
  .refine(
    (citation) => citation.end_index > citation.start_index,
    {
      message: "Citation end_index must be greater than start_index.",
      path: ["end_index"],
    },
  );

export const StructuredAnswerBasisSchema = z
  .object({
    kind: z.enum(["claim", "list_item"]),
    text: z.string().trim().min(1),
    citations: z.array(StructuredAnswerCitationSchema).default([]),
  })
  .strict();

export const StructuredAnswerSchema = z
  .object({
    text: z.string().trim().min(1),
    citations: z.array(StructuredAnswerCitationSchema).default([]),
    basis: z.array(StructuredAnswerBasisSchema).default([]),
  })
  .strict();

export const BackendAgentRunSuccessResponseSchema = z
  .object({
    run_id: z.string().trim().min(1),
    status: z.literal("completed"),
    final_answer: StructuredAnswerSchema,
    sources: z.array(RunSourceSchema),
    tool_call_count: z.number().int().nonnegative(),
    elapsed_ms: z.number().int().nonnegative(),
    metadata: z.object({
      tool_call_count: z.number().int().nonnegative(),
      elapsed_ms: z.number().int().nonnegative(),
    }).strict(),
  })
  .strict();

const RunHistoryTimestampSchema = z.string().datetime({ offset: true });
const RunHistoryRunIdSchema = z.string().trim().min(1);
const RunHistoryPayloadFieldSchema = z.enum([
  "tool_input",
  "tool_output",
  "error_output",
  "final_answer",
]);

export const RunHistoryEventTruncationSchema = z
  .object({
    eventSeq: z.number().int().nonnegative(),
    eventType: RunEventTypeSchema,
    fields: z.array(RunHistoryPayloadFieldSchema),
    omittedBytes: z.number().int().nonnegative(),
  })
  .strict();

export const RunHistoryRetentionMetadataSchema = z
  .object({
    maxRuns: z.number().int().positive(),
    maxEventsPerRun: z.number().int().positive(),
    maxPayloadBytes: z.number().int().positive(),
    duplicateEventsIgnored: z.number().int().nonnegative(),
    outOfOrderEventsRejected: z.number().int().nonnegative(),
    eventsDropped: z.number().int().nonnegative(),
    payloadTruncations: z.array(RunHistoryEventTruncationSchema),
  })
  .strict();

export const RunHistoryRunSummarySchema = z
  .object({
    runId: RunHistoryRunIdSchema,
    finalAnswer: z.string().nullable(),
    eventCount: z.number().int().nonnegative(),
    createdAt: RunHistoryTimestampSchema,
    updatedAt: RunHistoryTimestampSchema,
    latestEventSeq: z.number().int().nonnegative().nullable(),
    retention: RunHistoryRetentionMetadataSchema,
  })
  .strict();

export const RunHistoryRunSnapshotSchema = z
  .object({
    runId: RunHistoryRunIdSchema,
    finalAnswer: z.string().nullable(),
    events: RunEventListSchema,
    createdAt: RunHistoryTimestampSchema,
    updatedAt: RunHistoryTimestampSchema,
    retention: RunHistoryRetentionMetadataSchema,
  })
  .strict();

export const RunHistoryListResponseSchema = z
  .object({
    runs: z.array(RunHistoryRunSummarySchema),
  })
  .strict();

export const RunHistoryNotFoundErrorSchema = z
  .object({
    error: z
      .object({
        code: z.literal("RUN_HISTORY_NOT_FOUND"),
        message: z.string().trim().min(1),
      })
      .strict(),
  })
  .strict();

const RunEventTimestampSchema = z.number().int().nonnegative();
const RunIdSchema = z.string().trim().min(1);

export const RunStreamEventNameSchema = z.enum([
  "run_state",
  "retrieval_action",
  "tool_call",
  "run_complete",
  "run_error",
]);

export const RunEventToolNameSchema = z.enum(["web_search", "web_crawl"]);
export const RetrievalActionTypeSchema = z.enum([
  "search",
  "open_page",
  "find_in_page",
]);

export const RunStateEventSchema = z
  .object({
    runId: RunIdSchema,
    state: z.enum(["queued", "running", "completed", "failed"]),
    ts: RunEventTimestampSchema,
  })
  .strict();

const RetrievalActionEventBaseSchema = z
  .object({
    runId: RunIdSchema,
    actionId: z.string().trim().min(1),
    actionType: RetrievalActionTypeSchema,
    status: z.enum(["started", "completed", "failed"]),
    startedAt: RunEventTimestampSchema.optional(),
    endedAt: RunEventTimestampSchema.optional(),
    durationMs: z.number().nonnegative().optional(),
    title: z.string().trim().min(1).optional(),
    resultCount: z.number().int().nonnegative().optional(),
    matchCount: z.number().int().nonnegative().optional(),
    inputPreview: z.string().optional(),
    outputPreview: z.string().optional(),
    error: z.string().optional(),
  })
  .strict();

const SearchRetrievalActionEventSchema = RetrievalActionEventBaseSchema.extend({
  actionType: z.literal("search"),
  query: z.string().trim().min(1),
});

const OpenPageRetrievalActionEventSchema = RetrievalActionEventBaseSchema.extend({
  actionType: z.literal("open_page"),
  url: z.string().url(),
});

const FindInPageRetrievalActionEventSchema = RetrievalActionEventBaseSchema.extend({
  actionType: z.literal("find_in_page"),
  url: z.string().url(),
  pattern: z.string().trim().min(1),
});

export const RetrievalActionEventSchema = z.discriminatedUnion("actionType", [
  SearchRetrievalActionEventSchema,
  OpenPageRetrievalActionEventSchema,
  FindInPageRetrievalActionEventSchema,
]);

export const ToolCallEventSchema = z
  .object({
    runId: RunIdSchema,
    toolCallId: z.string().trim().min(1),
    toolName: RunEventToolNameSchema,
    status: z.enum(["started", "completed", "failed"]),
    startedAt: RunEventTimestampSchema.optional(),
    endedAt: RunEventTimestampSchema.optional(),
    durationMs: z.number().nonnegative().optional(),
    inputPreview: z.string().optional(),
    outputPreview: z.string().optional(),
    error: z.string().optional(),
  })
  .strict();

export const RunCompleteEventSchema = z
  .object({
    runId: RunIdSchema,
    finalAnswer: z.string(),
    structuredAnswer: StructuredAnswerSchema.optional(),
    sources: z.array(RunSourceSchema).default([]),
    completedAt: RunEventTimestampSchema,
    durationMs: z.number().nonnegative(),
  })
  .strict();

export const RunErrorEventSchema = z
  .object({
    runId: RunIdSchema,
    message: z.string().trim().min(1),
    code: z.string().trim().min(1).optional(),
    failedAt: RunEventTimestampSchema,
  })
  .strict();

export const RunStreamEventSchema = z.discriminatedUnion("event", [
  z.object({
    event: z.literal("run_state"),
    data: RunStateEventSchema,
  }).strict(),
  z.object({
    event: z.literal("retrieval_action"),
    data: RetrievalActionEventSchema,
  }).strict(),
  z.object({
    event: z.literal("tool_call"),
    data: ToolCallEventSchema,
  }).strict(),
  z.object({
    event: z.literal("run_complete"),
    data: RunCompleteEventSchema,
  }).strict(),
  z.object({
    event: z.literal("run_error"),
    data: RunErrorEventSchema,
  }).strict(),
]);

const RunStartErrorEnvelopeSchema = z
  .object({
    ok: z.literal(false),
    operation: z.literal("run_start"),
    durationMs: z.number().nonnegative(),
    request: RunStartRequestSchema.nullable(),
    error: FrontendErrorSchema,
  })
  .strict();

export const SearchApiEnvelopeSchema = z.union([
  SearchApiSuccessEnvelopeSchema,
  SearchApiErrorEnvelopeSchema,
]);

export const FetchApiEnvelopeSchema = z.union([
  FetchApiSuccessEnvelopeSchema,
  FetchApiErrorEnvelopeSchema,
]);

export const RunStartErrorEnvelope = RunStartErrorEnvelopeSchema;

export type SearchApiRequest = z.output<typeof SearchRequestSchema>;
export type FetchApiRequest = z.output<typeof FetchRequestSchema>;
export type RunMode = z.output<typeof RunModeSchema>;
export type RunStartRequest = z.output<typeof RunStartRequestSchema>;
export type RunRetrievalPolicy = z.output<typeof NormalizedRunRetrievalPolicySchema>;
export type RunStartResponse = z.output<typeof RunStartResponseSchema>;
export type RunSource = z.output<typeof RunSourceSchema>;
export type StructuredAnswerCitation = z.output<typeof StructuredAnswerCitationSchema>;
export type StructuredAnswerBasis = z.output<typeof StructuredAnswerBasisSchema>;
export type StructuredAnswer = z.output<typeof StructuredAnswerSchema>;
export type BackendAgentRunSuccessResponse = z.output<typeof BackendAgentRunSuccessResponseSchema>;
export type CanonicalRunEvent = RunEvent;
export type CanonicalRunEventType = RunEventType;
export type CanonicalRunEventToolName = CanonicalRunEventToolNameType;
export type CanonicalRunEventJson = RunEventJson;
export type CanonicalRunEventPayloadSignal = RunEventPayloadSignal;
export type CanonicalRunEventPayloadSafety = RunEventPayloadSafety;
export type CanonicalRunEventSafety = RunEventSafety;
export type CanonicalRunProgressStage = RunProgressStage;
export type CanonicalRunProgress = RunProgress;
export type CanonicalRunEventRetrievalActionKind = CanonicalRunEventRetrievalActionKindType;
export type CanonicalRunEventRetrievalAction = CanonicalRunEventRetrievalActionType;
export type RunHistoryEventTruncation = z.output<typeof RunHistoryEventTruncationSchema>;
export type RunHistoryRetentionMetadata = z.output<typeof RunHistoryRetentionMetadataSchema>;
export type RunHistoryRunSummary = z.output<typeof RunHistoryRunSummarySchema>;
export type RunHistoryRunSnapshot = z.output<typeof RunHistoryRunSnapshotSchema>;
export type RunHistoryListResponse = z.output<typeof RunHistoryListResponseSchema>;
export type RunHistoryNotFoundError = z.output<typeof RunHistoryNotFoundErrorSchema>;
export type RunStreamEventName = z.output<typeof RunStreamEventNameSchema>;
export type RunEventToolName = z.output<typeof RunEventToolNameSchema>;
export type RetrievalActionType = z.output<typeof RetrievalActionTypeSchema>;
export type RunStateEvent = z.output<typeof RunStateEventSchema>;
export type RetrievalActionEvent = z.output<typeof RetrievalActionEventSchema>;
export type ToolCallEvent = z.output<typeof ToolCallEventSchema>;
export type RunCompleteEvent = z.output<typeof RunCompleteEventSchema>;
export type RunErrorEvent = z.output<typeof RunErrorEventSchema>;
export type RunStreamEvent = z.output<typeof RunStreamEventSchema>;
export type FrontendErrorCode = z.output<typeof FrontendErrorCodeSchema>;
export type FrontendError = z.output<typeof FrontendErrorSchema>;
export type SearchApiEnvelope = z.output<typeof SearchApiEnvelopeSchema>;
export type FetchApiEnvelope = z.output<typeof FetchApiEnvelopeSchema>;
export type RunStartErrorEnvelope = z.output<typeof RunStartErrorEnvelopeSchema>;

export interface ErrorEnvelopeInput<TRequest> {
  operation: "search" | "fetch" | "run_start";
  request: TRequest | null;
  startedAt: number;
  error: unknown;
}

export function parseSearchApiRequest(input: unknown): SearchApiRequest {
  return SearchRequestSchema.parse(input);
}

export function parseFetchApiRequest(input: unknown): FetchApiRequest {
  return FetchRequestSchema.parse(input);
}

export function parseRunStartRequest(input: unknown): RunStartRequest {
  return RunStartRequestSchema.parse(input);
}

export function parseRunHistoryListResponse(input: unknown): RunHistoryListResponse {
  return RunHistoryListResponseSchema.parse(input);
}

export function parseRunHistoryRunSnapshot(input: unknown): RunHistoryRunSnapshot {
  return RunHistoryRunSnapshotSchema.parse(input);
}

export function parseRunHistoryNotFoundError(input: unknown): RunHistoryNotFoundError {
  return RunHistoryNotFoundErrorSchema.parse(input);
}

export function parseBackendAgentRunSuccessResponse(input: unknown): BackendAgentRunSuccessResponse {
  return BackendAgentRunSuccessResponseSchema.parse(input);
}

export function parseSearchSdkOptions(input: unknown): SearchOptions | undefined {
  const record = asRecord(input);
  if (record.options === undefined && record.retrievalPolicy === undefined) {
    return undefined;
  }
  return mergeRunPolicyIntoSearchInput(record.retrievalPolicy, record.options);
}

export function parseFetchSdkOptions(input: unknown): FetchOptions | undefined {
  const record = asRecord(input);
  if (record.options === undefined && record.retrievalPolicy === undefined) {
    return undefined;
  }
  return mergeRunPolicyIntoFetchInput(record.retrievalPolicy, record.options);
}

export function createSearchSuccessEnvelope(input: {
  request: SearchApiRequest;
  data: z.output<typeof SearchResponseSchema>;
  startedAt: number;
}): SearchApiEnvelope {
  return SearchApiEnvelopeSchema.parse({
    ok: true,
    operation: "search",
    durationMs: measureDurationMs(input.startedAt),
    request: input.request,
    data: input.data,
  });
}

export function createFetchSuccessEnvelope(input: {
  request: FetchApiRequest;
  data: z.output<typeof FetchResponseSchema>;
  startedAt: number;
}): FetchApiEnvelope {
  return FetchApiEnvelopeSchema.parse({
    ok: true,
    operation: "fetch",
    durationMs: measureDurationMs(input.startedAt),
    request: input.request,
    data: input.data,
  });
}

export function createRunStartResponse(
  input: RunStartResponse,
): RunStartResponse {
  return RunStartResponseSchema.parse(input);
}

export {
  createEmptyRunEventSafety,
  createRunEventKey,
  parseOrderedRunEventList,
  parseRunEvent,
  parseRunEventList,
  RunEventListSchema,
  RunEventSchema,
};

export function parseRunStreamEvent(input: unknown): RunStreamEvent {
  return RunStreamEventSchema.parse(input);
}

export function createErrorEnvelope<TRequest>(
  input: ErrorEnvelopeInput<TRequest>,
): SearchApiEnvelope | FetchApiEnvelope | RunStartErrorEnvelope {
  const envelope = {
    ok: false,
    operation: input.operation,
    durationMs: measureDurationMs(input.startedAt),
    request: input.request,
    error: normalizeFrontendError(input.error),
  };

  return input.operation === "search"
    ? SearchApiEnvelopeSchema.parse(envelope)
    : input.operation === "fetch"
      ? FetchApiEnvelopeSchema.parse(envelope)
      : RunStartErrorEnvelopeSchema.parse(envelope);
}

export function normalizeFrontendError(error: unknown): FrontendError {
  if (error instanceof ZodError) {
    return FrontendErrorSchema.parse({
      code: "VALIDATION_ERROR",
      message: "Request payload failed validation.",
      details: error.flatten(),
    });
  }

  if (isSdkError(error)) {
    return FrontendErrorSchema.parse({
      code: mapSdkErrorCode(error.kind),
      message: error.message,
      details: createSdkErrorDetails(error),
    });
  }

  return FrontendErrorSchema.parse({
    code: "INTERNAL_ERROR",
    message: "Unexpected error while executing request.",
  });
}

export function createRequestTimer(): number {
  return startCallTimer();
}

function mapSdkErrorCode(kind: SdkErrorKind): FrontendErrorCode {
  switch (kind) {
    case "rate_limited":
      return "RATE_LIMITED";
    case "timeout":
      return "TIMEOUT";
    case "network":
      return "NETWORK_ERROR";
    case "provider_unavailable":
      return "PROVIDER_UNAVAILABLE";
    case "invalid_request":
      return "INVALID_REQUEST";
    case "policy_denied":
      return "POLICY_DENIED";
    case "content_unavailable":
      return "CONTENT_UNAVAILABLE";
    case "unknown":
      return "INTERNAL_ERROR";
  }
}

function createSdkErrorDetails(error: SdkError): z.output<typeof FrontendSdkErrorDetailsSchema> {
  const details: z.input<typeof FrontendSdkErrorDetailsSchema> = {
    kind: error.kind,
    retryable: error.retryable,
    ...(error.statusCode !== undefined ? { statusCode: error.statusCode } : {}),
    ...(error.retryAfterMs !== undefined ? { retryAfterMs: error.retryAfterMs } : {}),
  };

  if (isFetchSafetyError(error)) {
    details.stage = error.stage;
    details.reason = error.reason;
    details.fallbackReason = error.fallbackReason;
    details.meta = error.meta;
    details.metadata = error.metadata;
  }

  return FrontendSdkErrorDetailsSchema.parse(details);
}

function isFetchSafetyError(error: SdkError): error is FetchSafetyError {
  return "operation" in error && error.operation === "fetch" && "stage" in error;
}

function asRecord(input: unknown): Record<string, unknown> {
  if (typeof input !== "object" || input === null || Array.isArray(input)) {
    return {};
  }

  return input as Record<string, unknown>;
}
