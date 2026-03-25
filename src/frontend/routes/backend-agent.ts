import {
  parseBackendAgentRunSuccessResponse,
  parseBackendDeepResearchQueuedResponse,
  parseBackendDeepResearchStatusResponse,
  type RunSource,
  type StructuredAnswer,
} from "../contracts.js";
import type { RunExecutor, RunExecutorContext, RunExecutorResult } from "./runs.js";

const DEFAULT_POLL_INTERVAL_MS = 250;

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
    if (response.status === 202 && context.mode === "deep_research") {
      const queued = parseBackendDeepResearchQueuedResponse(payload);
      return await pollDeepResearchRun({
        backendOrigin,
        fetchImplementation,
        delay,
        signal: context.signal,
        runId: queued.run_id,
      });
    }

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

async function pollDeepResearchRun(input: {
  backendOrigin: string;
  fetchImplementation: typeof fetch;
  delay: PollDelay;
  signal: AbortSignal;
  runId: string;
}): Promise<RunExecutorResult> {
  for (;;) {
    input.signal.throwIfAborted();
    const response = await input.fetchImplementation(
      new URL(`/api/agent/deep-research/${input.runId}`, input.backendOrigin),
      {
        method: "GET",
        signal: input.signal,
      },
    );
    const payload = await safelyReadJson(response);
    if (!response.ok) {
      return createBackendFailureResult(response.status, payload);
    }

    const status = parseBackendDeepResearchStatusResponse(payload);
    if (status.status === "completed" && status.final_answer !== null) {
      return createCompletedResult(status.final_answer, status.sources);
    }
    if (status.status === "failed") {
      return {
        status: "failed",
        message: status.error?.message ?? "Deep research failed.",
        code: "RUN_FAILED",
        failedAt: Date.now(),
      };
    }

    await input.delay(DEFAULT_POLL_INTERVAL_MS);
  }
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
