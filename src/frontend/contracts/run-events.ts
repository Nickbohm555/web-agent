import { z } from "zod";

export type RunEventJson =
  | string
  | number
  | boolean
  | null
  | RunEventJson[]
  | { [key: string]: RunEventJson };

export const RunEventIdSchema = z.string().trim().min(1);

export const RunEventSequenceSchema = z.number().int().nonnegative();

export const RunEventTimestampSchema = z.string().datetime({ offset: true });

export const RunEventTypeSchema = z.enum([
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
]);

export const RunEventToolNameSchema = z.enum(["web_search", "web_crawl"]);

export const RunEventJsonSchema: z.ZodType<RunEventJson> = z.lazy(() =>
  z.union([
    z.string(),
    z.number(),
    z.boolean(),
    z.null(),
    z.array(RunEventJsonSchema),
    z.record(z.string(), RunEventJsonSchema),
  ]),
);

export const RunEventPayloadSignalSchema = z
  .object({
    active: z.boolean(),
    paths: z.array(z.string()),
    reason: z.string().trim().min(1).optional(),
    omitted_bytes: z.number().int().nonnegative().optional(),
  })
  .strict();

export const RunEventPayloadSafetySchema = z
  .object({
    redaction: RunEventPayloadSignalSchema,
    truncation: RunEventPayloadSignalSchema,
  })
  .strict();

export const RunEventSafetySchema = z
  .object({
    tool_input: RunEventPayloadSafetySchema,
    tool_output: RunEventPayloadSafetySchema,
    error_output: RunEventPayloadSafetySchema,
  })
  .strict();

export const RunProgressStageSchema = z.enum([
  "planning",
  "search",
  "crawl",
  "verification",
  "source_expansion",
  "synthesis",
]);

export const RunEventRetrievalActionTypeSchema = z.enum([
  "search",
  "open_page",
  "find_in_page",
]);

export const RunEventRetrievalActionSchema = z
  .object({
    action_id: z.string().trim().min(1),
    action_type: RunEventRetrievalActionTypeSchema,
    query: z.string().trim().min(1).optional(),
    url: z.string().url().optional(),
    pattern: z.string().trim().min(1).optional(),
    result_count: z.number().int().nonnegative().optional(),
    match_count: z.number().int().nonnegative().optional(),
  })
  .strict()
  .superRefine((action, ctx) => {
    if (action.action_type === "search" && action.query === undefined) {
      ctx.addIssue({
        code: "custom",
        message: "Search retrieval actions must include a query.",
        path: ["query"],
      });
    }

    if (action.action_type === "open_page" && action.url === undefined) {
      ctx.addIssue({
        code: "custom",
        message: "Open-page retrieval actions must include a url.",
        path: ["url"],
      });
    }

    if (action.action_type === "find_in_page") {
      if (action.url === undefined) {
        ctx.addIssue({
          code: "custom",
          message: "Find-in-page retrieval actions must include a url.",
          path: ["url"],
        });
      }

      if (action.pattern === undefined) {
        ctx.addIssue({
          code: "custom",
          message: "Find-in-page retrieval actions must include a pattern.",
          path: ["pattern"],
        });
      }
    }
  });

export const RunProgressSchema = z
  .object({
    stage: RunProgressStageSchema,
    message: z.string().trim().min(1),
    completed: z.number().int().nonnegative().optional(),
    total: z.number().int().positive().optional(),
  })
  .strict()
  .superRefine((progress, ctx) => {
    if (progress.completed !== undefined && progress.total !== undefined && progress.completed > progress.total) {
      ctx.addIssue({
        code: "custom",
        message: "Progress completed cannot exceed total.",
        path: ["completed"],
      });
    }
  });

const RunEventBaseSchema = z
  .object({
    run_id: RunEventIdSchema,
    event_seq: RunEventSequenceSchema,
    ts: RunEventTimestampSchema,
    tool_name: RunEventToolNameSchema.optional(),
    tool_call_id: z.string().trim().min(1).optional(),
    tool_input: RunEventJsonSchema.optional(),
    tool_output: RunEventJsonSchema.optional(),
    error_output: RunEventJsonSchema.optional(),
    final_answer: z.string().optional(),
    progress: RunProgressSchema.optional(),
    retrieval_action: RunEventRetrievalActionSchema.optional(),
    safety: RunEventSafetySchema,
  })
  .strict();

const RunStartedEventSchema = RunEventBaseSchema.extend({
  event_type: z.literal("run_started"),
  tool_input: RunEventJsonSchema.optional(),
});

const ResearchPlanningStartedEventSchema = RunEventBaseSchema.extend({
  event_type: z.literal("research_planning_started"),
  progress: RunProgressSchema.refine((progress) => progress.stage === "planning", {
    message: "Planning progress events must use the planning stage.",
  }),
  tool_input: RunEventJsonSchema.optional(),
});

const ResearchSearchStartedEventSchema = RunEventBaseSchema.extend({
  event_type: z.literal("research_search_started"),
  progress: RunProgressSchema.refine((progress) => progress.stage === "search", {
    message: "Search progress events must use the search stage.",
  }),
  tool_input: RunEventJsonSchema.optional(),
  tool_output: RunEventJsonSchema.optional(),
});

const ResearchCrawlStartedEventSchema = RunEventBaseSchema.extend({
  event_type: z.literal("research_crawl_started"),
  progress: RunProgressSchema.refine((progress) => progress.stage === "crawl", {
    message: "Crawl progress events must use the crawl stage.",
  }),
  tool_input: RunEventJsonSchema.optional(),
  tool_output: RunEventJsonSchema.optional(),
});

const ResearchVerificationStartedEventSchema = RunEventBaseSchema.extend({
  event_type: z.literal("research_verification_started"),
  progress: RunProgressSchema.refine((progress) => progress.stage === "verification", {
    message: "Verification progress events must use the verification stage.",
  }),
  tool_input: RunEventJsonSchema.optional(),
  tool_output: RunEventJsonSchema.optional(),
});

const ResearchSourcesExpandedEventSchema = RunEventBaseSchema.extend({
  event_type: z.literal("research_sources_expanded"),
  progress: RunProgressSchema.refine((progress) => progress.stage === "source_expansion", {
    message: "Source expansion progress events must use the source_expansion stage.",
  }),
  tool_output: RunEventJsonSchema.optional(),
});

const ResearchSynthesisStartedEventSchema = RunEventBaseSchema.extend({
  event_type: z.literal("research_synthesis_started"),
  progress: RunProgressSchema.refine((progress) => progress.stage === "synthesis", {
    message: "Synthesis progress events must use the synthesis stage.",
  }),
  tool_output: RunEventJsonSchema.optional(),
});

const RetrievalActionStartedEventSchema = RunEventBaseSchema.extend({
  event_type: z.literal("retrieval_action_started"),
  retrieval_action: RunEventRetrievalActionSchema,
  tool_input: RunEventJsonSchema.optional(),
});

const RetrievalActionSucceededEventSchema = RunEventBaseSchema.extend({
  event_type: z.literal("retrieval_action_succeeded"),
  retrieval_action: RunEventRetrievalActionSchema,
  tool_output: RunEventJsonSchema.optional(),
});

const RetrievalActionFailedEventSchema = RunEventBaseSchema.extend({
  event_type: z.literal("retrieval_action_failed"),
  retrieval_action: RunEventRetrievalActionSchema,
  tool_input: RunEventJsonSchema.optional(),
  error_output: RunEventJsonSchema.optional(),
});

const ToolCallStartedEventSchema = RunEventBaseSchema.extend({
  event_type: z.literal("tool_call_started"),
  tool_name: RunEventToolNameSchema,
  tool_call_id: z.string().trim().min(1),
  tool_input: RunEventJsonSchema.optional(),
});

const ToolCallSucceededEventSchema = RunEventBaseSchema.extend({
  event_type: z.literal("tool_call_succeeded"),
  tool_name: RunEventToolNameSchema,
  tool_call_id: z.string().trim().min(1),
  tool_output: RunEventJsonSchema.optional(),
});

const ToolCallFailedEventSchema = RunEventBaseSchema.extend({
  event_type: z.literal("tool_call_failed"),
  tool_name: RunEventToolNameSchema,
  tool_call_id: z.string().trim().min(1),
  tool_input: RunEventJsonSchema.optional(),
  error_output: RunEventJsonSchema.optional(),
});

const FinalAnswerGeneratedEventSchema = RunEventBaseSchema.extend({
  event_type: z.literal("final_answer_generated"),
  final_answer: z.string(),
});

const RunCompletedEventSchema = RunEventBaseSchema.extend({
  event_type: z.literal("run_completed"),
  final_answer: z.string(),
});

const RunFailedEventSchema = RunEventBaseSchema.extend({
  event_type: z.literal("run_failed"),
  error_output: RunEventJsonSchema.optional(),
});

export const RunEventSchema = z
  .discriminatedUnion("event_type", [
    RunStartedEventSchema,
    ResearchPlanningStartedEventSchema,
    ResearchSearchStartedEventSchema,
    ResearchCrawlStartedEventSchema,
    ResearchVerificationStartedEventSchema,
    ResearchSourcesExpandedEventSchema,
    ResearchSynthesisStartedEventSchema,
    RetrievalActionStartedEventSchema,
    RetrievalActionSucceededEventSchema,
    RetrievalActionFailedEventSchema,
    ToolCallStartedEventSchema,
    ToolCallSucceededEventSchema,
    ToolCallFailedEventSchema,
    FinalAnswerGeneratedEventSchema,
    RunCompletedEventSchema,
    RunFailedEventSchema,
  ])
  .superRefine((event, ctx) => {
    validatePayloadSafety(event.tool_input, event.safety.tool_input, "tool_input", ctx);
    validatePayloadSafety(event.tool_output, event.safety.tool_output, "tool_output", ctx);
    validatePayloadSafety(event.error_output, event.safety.error_output, "error_output", ctx);
  });

export const RunEventListSchema = z.array(RunEventSchema);

export type RunEventType = z.output<typeof RunEventTypeSchema>;
export type RunEventToolName = z.output<typeof RunEventToolNameSchema>;
export type RunEventPayloadSignal = z.output<typeof RunEventPayloadSignalSchema>;
export type RunEventPayloadSafety = z.output<typeof RunEventPayloadSafetySchema>;
export type RunEventSafety = z.output<typeof RunEventSafetySchema>;
export type RunProgressStage = z.output<typeof RunProgressStageSchema>;
export type RunProgress = z.output<typeof RunProgressSchema>;
export type RunEventRetrievalActionType = z.output<typeof RunEventRetrievalActionTypeSchema>;
export type RunEventRetrievalAction = z.output<typeof RunEventRetrievalActionSchema>;
export type RunEvent = z.output<typeof RunEventSchema>;

export function parseRunEvent(input: unknown): RunEvent {
  return RunEventSchema.parse(input);
}

export function parseRunEventList(input: unknown): RunEvent[] {
  return RunEventListSchema.parse(input);
}

export function parseOrderedRunEventList(input: unknown): RunEvent[] {
  const events = parseRunEventList(input);

  for (let index = 1; index < events.length; index += 1) {
    const previous = events[index - 1];
    const current = events[index];

    if (previous === undefined || current === undefined) {
      continue;
    }

    if (previous.run_id === current.run_id && previous.event_seq >= current.event_seq) {
      throw new z.ZodError([
        {
          code: "custom",
          message: "Run events must be strictly increasing by event_seq within each run.",
          path: [index, "event_seq"],
        },
      ]);
    }
  }

  return events;
}

export function createEmptyRunEventSafety(): RunEventSafety {
  return {
    tool_input: createEmptyPayloadSafety(),
    tool_output: createEmptyPayloadSafety(),
    error_output: createEmptyPayloadSafety(),
  };
}

export function createRunEventKey(event: Pick<RunEvent, "run_id" | "event_seq">): string {
  return `${event.run_id}:${event.event_seq}`;
}

function createEmptyPayloadSafety(): RunEventPayloadSafety {
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

const REDACTION_SENTINEL = "[Redacted]";
const SENSITIVE_FIELD_NAMES = new Set(["authorization", "apiKey", "token"]);

function validatePayloadSafety(
  payload: RunEventJson | undefined,
  safety: RunEventPayloadSafety,
  field: "tool_input" | "tool_output" | "error_output",
  ctx: z.RefinementCtx,
) {
  validateSignalShape(safety.redaction, field, "redaction", ctx);
  validateSignalShape(safety.truncation, field, "truncation", ctx);

  if (payload === undefined) {
    return;
  }

  for (const sensitivePath of findSensitivePaths(payload)) {
    const value = readPath(payload, sensitivePath);
    if (value === REDACTION_SENTINEL) {
      if (!safety.redaction.active || !safety.redaction.paths.includes(sensitivePath)) {
        ctx.addIssue({
          code: "custom",
          message: "Redacted payload fields must include matching safety metadata.",
          path: ["safety", field, "redaction", "paths"],
        });
      }
      continue;
    }

    ctx.addIssue({
      code: "custom",
      message: "Sensitive payload fields must be redacted before rendering.",
      path: [field, ...toPathSegments(sensitivePath)],
    });
  }
}

function validateSignalShape(
  signal: RunEventPayloadSignal,
  field: "tool_input" | "tool_output" | "error_output",
  signalType: "redaction" | "truncation",
  ctx: z.RefinementCtx,
) {
  if (signal.active && signal.paths.length === 0) {
    ctx.addIssue({
      code: "custom",
      message: "Active payload safety markers must include at least one path.",
      path: ["safety", field, signalType, "paths"],
    });
  }

  if (!signal.active && signal.paths.length > 0) {
    ctx.addIssue({
      code: "custom",
      message: "Inactive payload safety markers cannot declare paths.",
      path: ["safety", field, signalType, "paths"],
    });
  }
}

function findSensitivePaths(payload: RunEventJson, prefix = ""): string[] {
  if (Array.isArray(payload)) {
    return payload.flatMap((value, index) => findSensitivePaths(value, joinPath(prefix, String(index))));
  }

  if (payload === null || typeof payload !== "object") {
    return [];
  }

  return Object.entries(payload).flatMap(([key, value]) => {
    const path = joinPath(prefix, key);
    const nested = findSensitivePaths(value, path);
    return SENSITIVE_FIELD_NAMES.has(key) ? [path, ...nested] : nested;
  });
}

function readPath(payload: RunEventJson, path: string): RunEventJson | undefined {
  let current: RunEventJson | undefined = payload;

  for (const segment of toPathSegments(path)) {
    if (current === null || typeof current !== "object") {
      return undefined;
    }

    current = Array.isArray(current)
      ? current[Number(segment)]
      : current[segment];
  }

  return current;
}

function joinPath(prefix: string, segment: string): string {
  return prefix.length === 0 ? segment : `${prefix}.${segment}`;
}

function toPathSegments(path: string): Array<string | number> {
  return path
    .split(".")
    .filter((segment) => segment.length > 0)
    .map((segment) => (/^\d+$/.test(segment) ? Number(segment) : segment));
}
