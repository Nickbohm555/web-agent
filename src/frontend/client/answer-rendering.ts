import {
  RunSourceSchema,
  StructuredAnswerSchema,
  type CanonicalRunEvent,
  type RunSource,
  type StructuredAnswer,
  type StructuredAnswerCitation,
} from "../contracts.js";

export interface AnswerTextSegment {
  kind: "text";
  text: string;
}

export interface AnswerCitationSegment {
  kind: "citation";
  text: string;
  citation: StructuredAnswerCitation;
  source: RunSource | null;
  citationNumber: number;
}

export type AnswerSegment = AnswerTextSegment | AnswerCitationSegment;

export interface ResolvedRunAnswer {
  text: string | null;
  structuredAnswer: StructuredAnswer | null;
  sources: RunSource[];
}

export function resolveRunAnswer(
  events: CanonicalRunEvent[],
  fallbackText: string | null,
): ResolvedRunAnswer {
  let structuredAnswer: StructuredAnswer | null = null;
  let sources: RunSource[] = [];

  for (const event of [...events].sort((left, right) => right.event_seq - left.event_seq)) {
    const payload = event.tool_output;
    if (payload === undefined || typeof payload !== "object" || payload === null) {
      continue;
    }

    const record = payload as Record<string, unknown>;
    if (structuredAnswer === null) {
      const parsedAnswer = StructuredAnswerSchema.safeParse(record.answer);
      if (parsedAnswer.success) {
        structuredAnswer = parsedAnswer.data;
      }
    }

    if (sources.length === 0) {
      const parsedSources = RunSourceSchema.array().safeParse(record.sources);
      if (parsedSources.success) {
        sources = parsedSources.data;
      }
    }

    if (structuredAnswer !== null && sources.length > 0) {
      break;
    }
  }

  return {
    text: structuredAnswer?.text ?? fallbackText,
    structuredAnswer,
    sources,
  };
}

export function segmentStructuredAnswer(
  answer: StructuredAnswer,
  sources: RunSource[],
): AnswerSegment[] {
  const sourceMap = new Map(sources.map((source) => [source.source_id, source]));
  const segments: AnswerSegment[] = [];
  let cursor = 0;

  for (const [index, citation] of answer.citations.entries()) {
    const safeStart = Math.max(cursor, citation.start_index);
    const safeEnd = Math.min(answer.text.length, citation.end_index);

    if (safeStart > cursor) {
      segments.push({
        kind: "text",
        text: answer.text.slice(cursor, safeStart),
      });
    }

    if (safeEnd > safeStart) {
      segments.push({
        kind: "citation",
        text: answer.text.slice(safeStart, safeEnd),
        citation,
        source: sourceMap.get(citation.source_id) ?? null,
        citationNumber: index + 1,
      });
    }

    cursor = Math.max(cursor, safeEnd);
  }

  if (cursor < answer.text.length) {
    segments.push({
      kind: "text",
      text: answer.text.slice(cursor),
    });
  }

  return segments;
}
