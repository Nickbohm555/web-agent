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

export const RunEventSchema = z
  .object({
    run_id: RunEventIdSchema,
    event_seq: RunEventSequenceSchema,
    event_type: RunEventTypeSchema,
    ts: RunEventTimestampSchema,
    tool_name: RunEventToolNameSchema.optional(),
    tool_call_id: z.string().trim().min(1).optional(),
    tool_input: RunEventJsonSchema.optional(),
    tool_output: RunEventJsonSchema.optional(),
    error_output: RunEventJsonSchema.optional(),
    final_answer: z.string().optional(),
    safety: RunEventSafetySchema,
  })
  .strict();

export const RunEventListSchema = z.array(RunEventSchema);

export type RunEventType = z.output<typeof RunEventTypeSchema>;
export type RunEventToolName = z.output<typeof RunEventToolNameSchema>;
export type RunEventPayloadSignal = z.output<typeof RunEventPayloadSignalSchema>;
export type RunEventPayloadSafety = z.output<typeof RunEventPayloadSafetySchema>;
export type RunEventSafety = z.output<typeof RunEventSafetySchema>;
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
