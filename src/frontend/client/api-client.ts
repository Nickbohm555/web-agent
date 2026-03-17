export interface RunStartRequest {
  prompt: string;
}

export interface RunStartResponse {
  runId: string;
  status: "queued" | "running";
}

interface RunStartErrorEnvelope {
  ok: false;
  operation: "run_start";
  durationMs: number;
  request: RunStartRequest | null;
  error: {
    code: string;
    message: string;
  };
}

export interface RunStartSuccessResult {
  ok: true;
  data: RunStartResponse;
}

export interface RunStartFailureResult {
  ok: false;
  message: string;
}

export type RunStartResult = RunStartSuccessResult | RunStartFailureResult;

export async function createRun(request: RunStartRequest): Promise<RunStartResult> {
  try {
    const response = await fetch("/api/runs", {
      method: "POST",
      headers: {
        "content-type": "application/json",
      },
      body: JSON.stringify(request),
    });

    const payload: unknown = await response.json();

    if (response.ok) {
      return {
        ok: true,
        data: parseRunStartResponse(payload),
      };
    }

    const envelope = parseRunStartErrorEnvelope(payload);
    return {
      ok: false,
      message: envelope.error.message,
    };
  } catch (error: unknown) {
    return {
      ok: false,
      message:
        error instanceof Error
          ? error.message
          : "Failed to start run.",
    };
  }
}

function parseRunStartResponse(input: unknown): RunStartResponse {
  const record = asRecord(input);
  if (
    typeof record.runId !== "string" ||
    (record.status !== "queued" && record.status !== "running")
  ) {
    throw new Error("Run start response failed validation.");
  }

  return {
    runId: record.runId,
    status: record.status,
  };
}

function parseRunStartErrorEnvelope(input: unknown): RunStartErrorEnvelope {
  const record = asRecord(input);
  const error = asRecord(record.error);

  if (
    record.ok !== false ||
    record.operation !== "run_start" ||
    typeof record.durationMs !== "number" ||
    (record.request !== null && !isRunStartRequest(record.request)) ||
    typeof error.code !== "string" ||
    typeof error.message !== "string"
  ) {
    throw new Error("Run start error response failed validation.");
  }

  return {
    ok: false,
    operation: "run_start",
    durationMs: record.durationMs,
    request: record.request ?? null,
    error: {
      code: error.code,
      message: error.message,
    },
  };
}

function isRunStartRequest(input: unknown): input is RunStartRequest {
  const record = asRecord(input);
  return typeof record.prompt === "string";
}

function asRecord(input: unknown): Record<string, unknown> {
  if (typeof input !== "object" || input === null || Array.isArray(input)) {
    return {};
  }

  return input as Record<string, unknown>;
}
