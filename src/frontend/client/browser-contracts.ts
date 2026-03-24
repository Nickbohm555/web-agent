export type RunMode = "quick" | "agentic" | "deep_research";

export interface RunRetrievalPolicy {
  search: {
    country: string;
    language: string;
    freshness: "day" | "week" | "month" | "year" | "any";
    domainScope: {
      includeDomains: string[];
      excludeDomains: string[];
    };
  };
  fetch: {
    maxAgeMs: number;
    fresh: boolean;
  };
}

export interface RunSource {
  source_id: string;
  title: string;
  url: string;
  snippet: string;
}

export interface StructuredAnswerCitation {
  source_id: string;
  title: string;
  url: string;
  start_index: number;
  end_index: number;
}

export interface StructuredAnswerBasis {
  kind: "claim" | "list_item";
  text: string;
  citations: StructuredAnswerCitation[];
}

export interface StructuredAnswer {
  text: string;
  citations: StructuredAnswerCitation[];
  basis: StructuredAnswerBasis[];
}

export interface RunStateEvent {
  runId: string;
  state: "queued" | "running" | "completed" | "failed";
  ts: number;
}

export type RetrievalActionEvent =
  | {
    runId: string;
    actionId: string;
    actionType: "search";
    status: "started" | "completed" | "failed";
    query: string;
    startedAt?: number | undefined;
    endedAt?: number | undefined;
    durationMs?: number | undefined;
    title?: string | undefined;
    resultCount?: number | undefined;
    matchCount?: number | undefined;
    inputPreview?: string | undefined;
    outputPreview?: string | undefined;
    error?: string | undefined;
  }
  | {
    runId: string;
    actionId: string;
    actionType: "open_page";
    status: "started" | "completed" | "failed";
    url: string;
    startedAt?: number | undefined;
    endedAt?: number | undefined;
    durationMs?: number | undefined;
    title?: string | undefined;
    resultCount?: number | undefined;
    matchCount?: number | undefined;
    inputPreview?: string | undefined;
    outputPreview?: string | undefined;
    error?: string | undefined;
  }
  | {
    runId: string;
    actionId: string;
    actionType: "find_in_page";
    status: "started" | "completed" | "failed";
    url: string;
    pattern: string;
    startedAt?: number | undefined;
    endedAt?: number | undefined;
    durationMs?: number | undefined;
    title?: string | undefined;
    resultCount?: number | undefined;
    matchCount?: number | undefined;
    inputPreview?: string | undefined;
    outputPreview?: string | undefined;
    error?: string | undefined;
  };

export interface ToolCallEvent {
  runId: string;
  toolCallId: string;
  toolName: "web_search" | "open_url";
  status: "started" | "completed" | "failed";
  startedAt?: number | undefined;
  endedAt?: number | undefined;
  durationMs?: number | undefined;
  inputPreview?: string | undefined;
  outputPreview?: string | undefined;
  error?: string | undefined;
}

export interface RunCompleteEvent {
  runId: string;
  finalAnswer: string;
  structuredAnswer?: StructuredAnswer | undefined;
  sources: RunSource[];
  completedAt: number;
  durationMs: number;
}

export interface RunErrorEvent {
  runId: string;
  message: string;
  code?: string | undefined;
  failedAt: number;
}

export type RunStreamEvent =
  | { event: "run_state"; data: RunStateEvent }
  | { event: "retrieval_action"; data: RetrievalActionEvent }
  | { event: "tool_call"; data: ToolCallEvent }
  | { event: "run_complete"; data: RunCompleteEvent }
  | { event: "run_error"; data: RunErrorEvent };

export type CanonicalRunEventPayloadSignal = {
  active: boolean;
  paths: string[];
  reason?: string | undefined;
  omitted_bytes?: number | undefined;
};

export type CanonicalRunEventPayloadSafety = {
  redaction: CanonicalRunEventPayloadSignal;
  truncation: CanonicalRunEventPayloadSignal;
};

export type CanonicalRunProgress = {
  stage:
    | "planning"
    | "search"
    | "crawl"
    | "verification"
    | "source_expansion"
    | "synthesis";
  message: string;
  completed?: number | undefined;
  total?: number | undefined;
};

export type CanonicalRunEvent = {
  run_id: string;
  event_seq: number;
  event_type:
    | "run_started"
    | "research_planning_started"
    | "research_search_started"
    | "research_crawl_started"
    | "research_verification_started"
    | "research_sources_expanded"
    | "research_synthesis_started"
    | "retrieval_action_started"
    | "retrieval_action_succeeded"
    | "retrieval_action_failed"
    | "tool_call_started"
    | "tool_call_succeeded"
    | "tool_call_failed"
    | "final_answer_generated"
    | "run_completed"
    | "run_failed";
  ts: string;
  tool_name?: "web_search" | "open_url" | undefined;
  tool_call_id?: string | undefined;
  tool_input?: unknown;
  tool_output?: unknown;
  error_output?: unknown;
  final_answer?: string | undefined;
  progress?: CanonicalRunProgress | undefined;
  retrieval_action?: {
    action_id: string;
    action_type: "search" | "open_page" | "find_in_page";
    query?: string | undefined;
    url?: string | undefined;
    pattern?: string | undefined;
    result_count?: number | undefined;
    match_count?: number | undefined;
  } | undefined;
  safety: {
    tool_input: CanonicalRunEventPayloadSafety;
    tool_output: CanonicalRunEventPayloadSafety;
    error_output: CanonicalRunEventPayloadSafety;
  };
};

export interface RunHistoryEventTruncation {
  eventSeq: number;
  eventType: CanonicalRunEvent["event_type"];
  fields: Array<"tool_input" | "tool_output" | "error_output" | "final_answer">;
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

export interface RunHistoryRunSummary {
  runId: string;
  finalAnswer: string | null;
  eventCount: number;
  createdAt: string;
  updatedAt: string;
  latestEventSeq: number | null;
  retention: RunHistoryRetentionMetadata;
}

export interface RunHistoryRunSnapshot {
  runId: string;
  finalAnswer: string | null;
  events: CanonicalRunEvent[];
  createdAt: string;
  updatedAt: string;
  retention: RunHistoryRetentionMetadata;
}

export interface RunHistoryListResponse {
  runs: RunHistoryRunSummary[];
}

type RecordLike = Record<string, unknown>;

export function parseRunStreamEvent(input: unknown): RunStreamEvent {
  const record = asRecord(input);
  const event = expectString(record.event, "event");
  const data = asRecord(record.data);

  switch (event) {
    case "run_state":
      return { event, data: parseRunStateEvent(data) };
    case "retrieval_action":
      return { event, data: parseRetrievalActionEvent(data) };
    case "tool_call":
      return { event, data: parseToolCallEvent(data) };
    case "run_complete":
      return { event, data: parseRunCompleteEvent(data) };
    case "run_error":
      return { event, data: parseRunErrorEvent(data) };
    default:
      throw new Error(`Unsupported run stream event '${event}'.`);
  }
}

export function parseRunHistoryListResponse(input: unknown): RunHistoryListResponse {
  const record = asRecord(input);
  return {
    runs: expectArray(record.runs, "runs").map((run, index) =>
      parseRunHistoryRunSummary(asRecord(run), `runs[${index}]`),
    ),
  };
}

export function parseRunHistoryRunSnapshot(input: unknown): RunHistoryRunSnapshot {
  const record = asRecord(input);
  return {
    runId: expectString(record.runId, "runId"),
    finalAnswer: parseNullableString(record.finalAnswer, "finalAnswer"),
    events: parseOrderedRunEventList(record.events),
    createdAt: expectString(record.createdAt, "createdAt"),
    updatedAt: expectString(record.updatedAt, "updatedAt"),
    retention: parseRunHistoryRetentionMetadata(record.retention, "retention"),
  };
}

export function parseOrderedRunEventList(input: unknown): CanonicalRunEvent[] {
  const events = expectArray(input, "events").map((event, index) =>
    parseCanonicalRunEvent(asRecord(event), `events[${index}]`),
  );

  for (let index = 1; index < events.length; index += 1) {
    const previous = events[index - 1];
    const current = events[index];
    if (
      previous !== undefined &&
      current !== undefined &&
      previous.run_id === current.run_id &&
      previous.event_seq >= current.event_seq
    ) {
      throw new Error("Run events must be strictly increasing by event_seq within each run.");
    }
  }

  return events;
}

export function parseStructuredAnswerOrNull(input: unknown): StructuredAnswer | null {
  try {
    return parseStructuredAnswer(input, "structuredAnswer");
  } catch {
    return null;
  }
}

export function parseRunSourceListOrNull(input: unknown): RunSource[] | null {
  try {
    return expectArray(input, "sources").map((source, index) =>
      parseRunSource(asRecord(source), `sources[${index}]`),
    );
  } catch {
    return null;
  }
}

export function createEmptyRunEventSafety(): CanonicalRunEvent["safety"] {
  return {
    tool_input: createEmptyPayloadSafety(),
    tool_output: createEmptyPayloadSafety(),
    error_output: createEmptyPayloadSafety(),
  };
}

export function createRunEventKey(
  event: Pick<CanonicalRunEvent, "run_id" | "event_seq">,
): string {
  return `${event.run_id}:${event.event_seq}`;
}

function parseRunStateEvent(record: RecordLike): RunStateEvent {
  return {
    runId: expectString(record.runId, "runId"),
    state: expectEnum(record.state, "state", [
      "queued",
      "running",
      "completed",
      "failed",
    ]),
    ts: expectNonNegativeNumber(record.ts, "ts"),
  };
}

function parseRetrievalActionEvent(record: RecordLike): RetrievalActionEvent {
  const base = {
    runId: expectString(record.runId, "runId"),
    actionId: expectString(record.actionId, "actionId"),
    status: expectEnum(record.status, "status", [
      "started",
      "completed",
      "failed",
    ]),
  };
  const actionType = expectEnum(record.actionType, "actionType", [
    "search",
    "open_page",
    "find_in_page",
  ]);

  switch (actionType) {
    case "search":
      return {
        ...base,
        actionType,
        query: expectString(record.query, "query"),
        ...includeOptionalNumber("startedAt", record.startedAt, "startedAt"),
        ...includeOptionalNumber("endedAt", record.endedAt, "endedAt"),
        ...includeOptionalNumber("durationMs", record.durationMs, "durationMs"),
        ...includeOptionalString("title", record.title, "title"),
        ...includeOptionalInteger("resultCount", record.resultCount, "resultCount"),
        ...includeOptionalInteger("matchCount", record.matchCount, "matchCount"),
        ...includeOptionalString("inputPreview", record.inputPreview, "inputPreview"),
        ...includeOptionalString("outputPreview", record.outputPreview, "outputPreview"),
        ...includeOptionalString("error", record.error, "error"),
      };
    case "open_page":
      return {
        ...base,
        actionType,
        url: expectString(record.url, "url"),
        ...includeOptionalNumber("startedAt", record.startedAt, "startedAt"),
        ...includeOptionalNumber("endedAt", record.endedAt, "endedAt"),
        ...includeOptionalNumber("durationMs", record.durationMs, "durationMs"),
        ...includeOptionalString("title", record.title, "title"),
        ...includeOptionalInteger("resultCount", record.resultCount, "resultCount"),
        ...includeOptionalInteger("matchCount", record.matchCount, "matchCount"),
        ...includeOptionalString("inputPreview", record.inputPreview, "inputPreview"),
        ...includeOptionalString("outputPreview", record.outputPreview, "outputPreview"),
        ...includeOptionalString("error", record.error, "error"),
      };
    case "find_in_page":
      return {
        ...base,
        actionType,
        url: expectString(record.url, "url"),
        pattern: expectString(record.pattern, "pattern"),
        ...includeOptionalNumber("startedAt", record.startedAt, "startedAt"),
        ...includeOptionalNumber("endedAt", record.endedAt, "endedAt"),
        ...includeOptionalNumber("durationMs", record.durationMs, "durationMs"),
        ...includeOptionalString("title", record.title, "title"),
        ...includeOptionalInteger("resultCount", record.resultCount, "resultCount"),
        ...includeOptionalInteger("matchCount", record.matchCount, "matchCount"),
        ...includeOptionalString("inputPreview", record.inputPreview, "inputPreview"),
        ...includeOptionalString("outputPreview", record.outputPreview, "outputPreview"),
        ...includeOptionalString("error", record.error, "error"),
      };
  }
}

function parseToolCallEvent(record: RecordLike): ToolCallEvent {
  return {
    runId: expectString(record.runId, "runId"),
    toolCallId: expectString(record.toolCallId, "toolCallId"),
    toolName: expectEnum(record.toolName, "toolName", ["web_search", "open_url"]),
    status: expectEnum(record.status, "status", [
      "started",
      "completed",
      "failed",
    ]),
    ...includeOptionalNumber("startedAt", record.startedAt, "startedAt"),
    ...includeOptionalNumber("endedAt", record.endedAt, "endedAt"),
    ...includeOptionalNumber("durationMs", record.durationMs, "durationMs"),
    ...includeOptionalString("inputPreview", record.inputPreview, "inputPreview"),
    ...includeOptionalString("outputPreview", record.outputPreview, "outputPreview"),
    ...includeOptionalString("error", record.error, "error"),
  };
}

function parseRunCompleteEvent(record: RecordLike): RunCompleteEvent {
  const structuredAnswer =
    record.structuredAnswer === undefined
      ? undefined
      : parseStructuredAnswer(record.structuredAnswer, "structuredAnswer");

  return {
    runId: expectString(record.runId, "runId"),
    finalAnswer: expectString(record.finalAnswer, "finalAnswer"),
    sources: expectArray(record.sources, "sources").map((source, index) =>
      parseRunSource(asRecord(source), `sources[${index}]`),
    ),
    completedAt: expectNonNegativeNumber(record.completedAt, "completedAt"),
    durationMs: expectNonNegativeNumber(record.durationMs, "durationMs"),
    ...includeDefined("structuredAnswer", structuredAnswer),
  };
}

function parseRunErrorEvent(record: RecordLike): RunErrorEvent {
  return {
    runId: expectString(record.runId, "runId"),
    message: expectString(record.message, "message"),
    failedAt: expectNonNegativeNumber(record.failedAt, "failedAt"),
    ...includeOptionalString("code", record.code, "code"),
  };
}

function parseRunHistoryRunSummary(
  record: RecordLike,
  path: string,
): RunHistoryRunSummary {
  return {
    runId: expectString(record.runId, `${path}.runId`),
    finalAnswer: parseNullableString(record.finalAnswer, `${path}.finalAnswer`),
    eventCount: expectInteger(record.eventCount, `${path}.eventCount`),
    createdAt: expectString(record.createdAt, `${path}.createdAt`),
    updatedAt: expectString(record.updatedAt, `${path}.updatedAt`),
    latestEventSeq:
      record.latestEventSeq === null
        ? null
        : expectInteger(record.latestEventSeq, `${path}.latestEventSeq`),
    retention: parseRunHistoryRetentionMetadata(
      record.retention,
      `${path}.retention`,
    ),
  };
}

function parseRunHistoryRetentionMetadata(
  input: unknown,
  path: string,
): RunHistoryRetentionMetadata {
  const record = asRecord(input);
  return {
    maxRuns: expectInteger(record.maxRuns, `${path}.maxRuns`),
    maxEventsPerRun: expectInteger(record.maxEventsPerRun, `${path}.maxEventsPerRun`),
    maxPayloadBytes: expectInteger(record.maxPayloadBytes, `${path}.maxPayloadBytes`),
    duplicateEventsIgnored: expectInteger(
      record.duplicateEventsIgnored,
      `${path}.duplicateEventsIgnored`,
    ),
    outOfOrderEventsRejected: expectInteger(
      record.outOfOrderEventsRejected,
      `${path}.outOfOrderEventsRejected`,
    ),
    eventsDropped: expectInteger(record.eventsDropped, `${path}.eventsDropped`),
    payloadTruncations: expectArray(record.payloadTruncations, `${path}.payloadTruncations`).map(
      (truncation, index) => parseRunHistoryEventTruncation(
        asRecord(truncation),
        `${path}.payloadTruncations[${index}]`,
      ),
    ),
  };
}

function parseRunHistoryEventTruncation(
  record: RecordLike,
  path: string,
): RunHistoryEventTruncation {
  return {
    eventSeq: expectInteger(record.eventSeq, `${path}.eventSeq`),
    eventType: expectEnum(record.eventType, `${path}.eventType`, [
      "run_started",
      "research_planning_started",
      "research_search_started",
      "research_crawl_started",
      "research_verification_started",
      "research_sources_expanded",
      "research_synthesis_started",
      "retrieval_action_started",
      "retrieval_action_succeeded",
      "retrieval_action_failed",
      "tool_call_started",
      "tool_call_succeeded",
      "tool_call_failed",
      "final_answer_generated",
      "run_completed",
      "run_failed",
    ]),
    fields: expectArray(record.fields, `${path}.fields`).map((field, index) =>
      expectEnum(field, `${path}.fields[${index}]`, [
        "tool_input",
        "tool_output",
        "error_output",
        "final_answer",
      ]),
    ),
    omittedBytes: expectInteger(record.omittedBytes, `${path}.omittedBytes`),
  };
}

function parseCanonicalRunEvent(record: RecordLike, path: string): CanonicalRunEvent {
  const progress =
    record.progress === undefined
      ? undefined
      : parseRunProgress(asRecord(record.progress), `${path}.progress`);
  const retrievalAction =
    record.retrieval_action === undefined
      ? undefined
      : parseCanonicalRetrievalAction(
        asRecord(record.retrieval_action),
        `${path}.retrieval_action`,
      );

  return {
    run_id: expectString(record.run_id, `${path}.run_id`),
    event_seq: expectInteger(record.event_seq, `${path}.event_seq`),
    event_type: expectEnum(record.event_type, `${path}.event_type`, [
      "run_started",
      "research_planning_started",
      "research_search_started",
      "research_crawl_started",
      "research_verification_started",
      "research_sources_expanded",
      "research_synthesis_started",
      "retrieval_action_started",
      "retrieval_action_succeeded",
      "retrieval_action_failed",
      "tool_call_started",
      "tool_call_succeeded",
      "tool_call_failed",
      "final_answer_generated",
      "run_completed",
      "run_failed",
    ]),
    ts: expectString(record.ts, `${path}.ts`),
    safety: parseRunEventSafety(record.safety, `${path}.safety`),
    ...includeOptionalEnum(
      "tool_name",
      record.tool_name,
      `${path}.tool_name`,
      ["web_search", "open_url"],
    ),
    ...includeOptionalString("tool_call_id", record.tool_call_id, `${path}.tool_call_id`),
    ...includeDefined("tool_input", record.tool_input),
    ...includeDefined("tool_output", record.tool_output),
    ...includeDefined("error_output", record.error_output),
    ...includeOptionalString("final_answer", record.final_answer, `${path}.final_answer`),
    ...includeDefined("progress", progress),
    ...includeDefined("retrieval_action", retrievalAction),
  };
}

function parseRunProgress(record: RecordLike, path: string): CanonicalRunProgress {
  return {
    stage: expectEnum(record.stage, `${path}.stage`, [
      "planning",
      "search",
      "crawl",
      "verification",
      "source_expansion",
      "synthesis",
    ]),
    message: expectString(record.message, `${path}.message`),
    ...includeOptionalInteger("completed", record.completed, `${path}.completed`),
    ...includeOptionalInteger("total", record.total, `${path}.total`),
  };
}

function parseCanonicalRetrievalAction(
  record: RecordLike,
  path: string,
): NonNullable<CanonicalRunEvent["retrieval_action"]> {
  return {
    action_id: expectString(record.action_id, `${path}.action_id`),
    action_type: expectEnum(record.action_type, `${path}.action_type`, [
      "search",
      "open_page",
      "find_in_page",
    ]),
    ...includeOptionalString("query", record.query, `${path}.query`),
    ...includeOptionalString("url", record.url, `${path}.url`),
    ...includeOptionalString("pattern", record.pattern, `${path}.pattern`),
    ...includeOptionalInteger("result_count", record.result_count, `${path}.result_count`),
    ...includeOptionalInteger("match_count", record.match_count, `${path}.match_count`),
  };
}

function parseRunEventSafety(
  input: unknown,
  path: string,
): CanonicalRunEvent["safety"] {
  const record = asRecord(input);
  return {
    tool_input: parsePayloadSafety(record.tool_input, `${path}.tool_input`),
    tool_output: parsePayloadSafety(record.tool_output, `${path}.tool_output`),
    error_output: parsePayloadSafety(record.error_output, `${path}.error_output`),
  };
}

function parsePayloadSafety(
  input: unknown,
  path: string,
): CanonicalRunEventPayloadSafety {
  const record = asRecord(input);
  return {
    redaction: parsePayloadSignal(record.redaction, `${path}.redaction`),
    truncation: parsePayloadSignal(record.truncation, `${path}.truncation`),
  };
}

function parsePayloadSignal(
  input: unknown,
  path: string,
): CanonicalRunEventPayloadSignal {
  const record = asRecord(input);
  return {
    active: expectBoolean(record.active, `${path}.active`),
    paths: expectArray(record.paths, `${path}.paths`).map((value, index) =>
      expectString(value, `${path}.paths[${index}]`),
    ),
    ...includeOptionalString("reason", record.reason, `${path}.reason`),
    ...includeOptionalInteger("omitted_bytes", record.omitted_bytes, `${path}.omitted_bytes`),
  };
}

function parseStructuredAnswer(input: unknown, path: string): StructuredAnswer {
  const record = asRecord(input);
  return {
    text: expectString(record.text, `${path}.text`),
    citations: expectArray(record.citations ?? [], `${path}.citations`).map((citation, index) =>
      parseStructuredAnswerCitation(asRecord(citation), `${path}.citations[${index}]`),
    ),
    basis: expectArray(record.basis ?? [], `${path}.basis`).map((basisItem, index) =>
      parseStructuredAnswerBasis(asRecord(basisItem), `${path}.basis[${index}]`),
    ),
  };
}

function parseStructuredAnswerCitation(
  record: RecordLike,
  path: string,
): StructuredAnswerCitation {
  const url = expectUrl(record.url, `${path}.url`);
  const startIndex = expectInteger(record.start_index, `${path}.start_index`);
  const endIndex = expectInteger(record.end_index, `${path}.end_index`);
  if (endIndex <= startIndex) {
    throw new Error(`Expected end_index to be greater than start_index at ${path}.`);
  }

  return {
    source_id: expectString(record.source_id, `${path}.source_id`),
    title: expectNonEmptyString(record.title, `${path}.title`),
    url,
    start_index: startIndex,
    end_index: endIndex,
  };
}

function parseStructuredAnswerBasis(
  record: RecordLike,
  path: string,
): StructuredAnswerBasis {
  return {
    kind: expectEnum(record.kind, `${path}.kind`, ["claim", "list_item"]),
    text: expectString(record.text, `${path}.text`),
    citations: expectArray(record.citations ?? [], `${path}.citations`).map((citation, index) =>
      parseStructuredAnswerCitation(asRecord(citation), `${path}.citations[${index}]`),
    ),
  };
}

function parseRunSource(record: RecordLike, path: string): RunSource {
  return {
    source_id: expectString(record.source_id, `${path}.source_id`),
    title: expectNonEmptyString(record.title, `${path}.title`),
    url: expectUrl(record.url, `${path}.url`),
    snippet: expectString(record.snippet, `${path}.snippet`),
  };
}

function createEmptyPayloadSafety(): CanonicalRunEventPayloadSafety {
  return {
    redaction: {
      active: false,
      paths: [],
    },
    truncation: {
      active: false,
      paths: [],
    },
  };
}

function asRecord(input: unknown): RecordLike {
  if (typeof input !== "object" || input === null || Array.isArray(input)) {
    throw new Error("Expected object.");
  }

  return input as RecordLike;
}

function expectArray(input: unknown, path: string): unknown[] {
  if (!Array.isArray(input)) {
    throw new Error(`Expected array at ${path}.`);
  }

  return input;
}

function expectString(input: unknown, path: string): string {
  if (typeof input !== "string") {
    throw new Error(`Expected string at ${path}.`);
  }

  return input;
}

function expectNonEmptyString(input: unknown, path: string): string {
  const value = expectString(input, path);
  if (value.trim().length === 0) {
    throw new Error(`Expected non-empty string at ${path}.`);
  }

  return value;
}

function parseOptionalString(input: unknown, path: string): string | undefined {
  if (input === undefined) {
    return undefined;
  }

  return expectString(input, path);
}

function parseNullableString(input: unknown, path: string): string | null {
  if (input === null) {
    return null;
  }

  return expectString(input, path);
}

function expectBoolean(input: unknown, path: string): boolean {
  if (typeof input !== "boolean") {
    throw new Error(`Expected boolean at ${path}.`);
  }

  return input;
}

function expectUrl(input: unknown, path: string): string {
  const value = expectString(input, path);
  try {
    new URL(value);
    return value;
  } catch {
    throw new Error(`Expected URL at ${path}.`);
  }
}

function expectInteger(input: unknown, path: string): number {
  if (typeof input !== "number" || !Number.isInteger(input) || input < 0) {
    throw new Error(`Expected non-negative integer at ${path}.`);
  }

  return input;
}

function parseOptionalInteger(input: unknown, path: string): number | undefined {
  if (input === undefined) {
    return undefined;
  }

  return expectInteger(input, path);
}

function expectNonNegativeNumber(input: unknown, path: string): number {
  if (typeof input !== "number" || Number.isNaN(input) || input < 0) {
    throw new Error(`Expected non-negative number at ${path}.`);
  }

  return input;
}

function parseOptionalNonNegativeNumber(
  input: unknown,
  path: string,
): number | undefined {
  if (input === undefined) {
    return undefined;
  }

  return expectNonNegativeNumber(input, path);
}

function expectEnum<T extends string>(
  input: unknown,
  path: string,
  values: readonly T[],
): T {
  if (typeof input !== "string" || !values.includes(input as T)) {
    throw new Error(`Expected one of ${values.join(", ")} at ${path}.`);
  }

  return input as T;
}

function includeDefined<T>(
  key: string,
  value: T | undefined,
): Record<string, T> | Record<string, never> {
  return value === undefined ? {} : { [key]: value };
}

function includeOptionalString(
  key: string,
  value: unknown,
  path: string,
): Record<string, string> | Record<string, never> {
  const parsed = parseOptionalString(value, path);
  return includeDefined(key, parsed);
}

function includeOptionalInteger(
  key: string,
  value: unknown,
  path: string,
): Record<string, number> | Record<string, never> {
  const parsed = parseOptionalInteger(value, path);
  return includeDefined(key, parsed);
}

function includeOptionalNumber(
  key: string,
  value: unknown,
  path: string,
): Record<string, number> | Record<string, never> {
  const parsed = parseOptionalNonNegativeNumber(value, path);
  return includeDefined(key, parsed);
}

function includeOptionalEnum<T extends string>(
  key: string,
  value: unknown,
  path: string,
  values: readonly T[],
): Record<string, T> | Record<string, never> {
  if (value === undefined) {
    return {};
  }

  return { [key]: expectEnum(value, path, values) };
}
