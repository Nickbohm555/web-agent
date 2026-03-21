import type { AddressInfo } from "node:net";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const randomUuidMock = vi.fn();

vi.mock("node:crypto", async () => {
  const actual = await vi.importActual<typeof import("node:crypto")>(
    "node:crypto",
  );

  return {
    ...actual,
    randomUUID: randomUuidMock,
  };
});

describe("run start API contracts", () => {
  beforeEach(() => {
    randomUuidMock.mockReset();
    randomUuidMock.mockReturnValue("123e4567-e89b-12d3-a456-426614174000");
    vi.resetModules();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("returns a typed run-start response for valid payloads", async () => {
    const { RunStartResponseSchema } = await import("../../frontend/contracts.js");

    const response = await callRoute({
      prompt: "  Find recent agent tooling updates  ",
      mode: "quick",
    });

    expect(response.status).toBe(201);
    expect(RunStartResponseSchema.parse(response.json)).toEqual({
      runId: "123e4567-e89b-12d3-a456-426614174000",
      status: "queued",
    });
  });

  it("returns a validation envelope for malformed payloads", async () => {
    const { RunStartErrorEnvelope } = await import("../../frontend/contracts.js");

    const response = await callRoute({
      prompt: "   ",
      mode: "agentic",
    });

    expect(response.status).toBe(400);

    const envelope = RunStartErrorEnvelope.parse(response.json);
    expect(envelope.ok).toBe(false);
    expect(envelope.operation).toBe("run_start");
    expect(envelope.request).toBeNull();
    expect(envelope.error.code).toBe("VALIDATION_ERROR");

    if (envelope.error.details && "fieldErrors" in envelope.error.details) {
      expect(envelope.error.details.fieldErrors.prompt).toBeDefined();
    } else {
      throw new Error("Expected validation error details.");
    }
  });

  it("rejects unknown run modes with explicit validation details", async () => {
    const { RunStartErrorEnvelope } = await import("../../frontend/contracts.js");

    const response = await callRoute({
      prompt: "Find sources",
      mode: "turbo",
    });

    expect(response.status).toBe(400);

    const envelope = RunStartErrorEnvelope.parse(response.json);
    expect(envelope.ok).toBe(false);
    expect(envelope.error.code).toBe("VALIDATION_ERROR");

    if (envelope.error.details && "fieldErrors" in envelope.error.details) {
      expect(envelope.error.details.fieldErrors.mode).toBeDefined();
    } else {
      throw new Error("Expected validation error details.");
    }
  });
});

async function callRoute(
  payload: unknown,
): Promise<{ status: number; json: unknown }> {
  const { createFrontendServerApp } = await import("../../frontend/server.js");
  const app = createFrontendServerApp();
  const server = await new Promise<import("node:http").Server>((resolve) => {
    const listeningServer = app.listen(0, "127.0.0.1", () => {
      resolve(listeningServer);
    });
  });

  const address = server.address() as AddressInfo;

  try {
    const response = await fetch(`http://127.0.0.1:${address.port}/api/runs`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    return {
      status: response.status,
      json: await response.json(),
    };
  } finally {
    await new Promise<void>((resolve, reject) => {
      server.close((error) => {
        if (error) {
          reject(error);
          return;
        }

        resolve();
      });
    });
  }
}
