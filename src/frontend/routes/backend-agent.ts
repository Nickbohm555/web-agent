import {
  parseBackendAgentRunSuccessResponse,
  type RunSource,
  type StructuredAnswer,
} from "../contracts.js";
import type { RunExecutor, RunExecutorContext, RunExecutorResult } from "./runs.js";

export type PollDelay = (ms: number) => Promise<void>;

export function createHttpAgentRunExecutor(
  backendOrigin: string,
  fetchImplementation: typeof fetch = fetch,
  delay: PollDelay = delayForPoll,
): RunExecutor {
  return async function httpAgentRunExecutor(
    context: RunExecutorContext,
  ): Promise<RunExecutorResult> {
    const response = await fetchImplementation(
      new URL("/api/agent/run", backendOrigin),
      {
        method: "POST",
        headers: {
          "content-type": "application/json",
        },
        body: JSON.stringify({
          prompt: context.prompt,
          mode: context.mode,
          ...(context.threadId ? { thread_id: context.threadId } : {}),
        }),
        signal: context.signal,
      },
    );

    const payload = await safelyReadJson(response);

    if (response.ok) {
      const responseRecord = parseBackendAgentRunSuccessResponse(payload);

      return {
        status: "completed",
        finalAnswer: responseRecord.final_answer.text,
        structuredAnswer: responseRecord.final_answer,
        sources: responseRecord.sources,
        durationMs: responseRecord.elapsed_ms,
        completedAt: Date.now(),
      };
    }

    return createBackendFailureResult(response.status, payload);
  };
}
function createCompletedResult(
  finalAnswer: StructuredAnswer,
  sources: RunSource[],
): RunExecutorResult {
  return {
    status: "completed",
    finalAnswer: finalAnswer.text,
    structuredAnswer: finalAnswer,
    sources,
    completedAt: Date.now(),
  };
}

function createBackendFailureResult(statusCode: number, payload: unknown): RunExecutorResult {
  const errorPayload = asRecord(asRecord(payload).error);
  return {
    status: "failed",
    message:
      typeof errorPayload.message === "string"
        ? errorPayload.message
        : `Backend agent route failed with status ${statusCode}.`,
    code:
      typeof errorPayload.code === "string"
        ? errorPayload.code
        : "RUN_FAILED",
    failedAt: Date.now(),
  };
}

async function delayForPoll(ms: number): Promise<void> {
  await new Promise<void>((resolve) => {
    setTimeout(resolve, ms);
  });
}

async function safelyReadJson(response: Response): Promise<unknown> {
  const contentType = response.headers.get("content-type") ?? "";
  if (!contentType.includes("application/json")) {
    return null;
  }

  try {
    return await response.json();
  } catch {
    return null;
  }
}

function asRecord(value: unknown): Record<string, unknown> {
  if (typeof value !== "object" || value === null) {
    return {};
  }

  return value as Record<string, unknown>;
}
