import { describe, expect, it, vi } from "vitest";

import {
  buildCallMeta,
  measureDurationMs,
  startCallTimer,
} from "../../../core/telemetry/call-meta.js";

describe("call meta", () => {
  it("builds stable metadata with monotonic timing and optional usage namespaces", () => {
    vi.spyOn(performance, "now")
      .mockReturnValueOnce(100)
      .mockReturnValueOnce(145.6789);

    const startedAt = startCallTimer();
    const meta = buildCallMeta({
      operation: "search",
      startedAt,
      attempts: 3,
      retries: 2,
      cacheHit: false,
      timings: {
        providerMs: 40.1234,
        mappingMs: 5.4321,
      },
      usage: {
        provider: {
          organicResults: 12,
        },
      },
    });

    expect(meta).toEqual({
      operation: "search",
      durationMs: 45.679,
      attempts: 3,
      retries: 2,
      cacheHit: false,
      timings: {
        providerMs: 40.123,
        mappingMs: 5.432,
      },
      usage: {
        provider: {
          organicResults: 12,
        },
      },
    });
  });

  it("clamps negative or invalid durations to zero", () => {
    expect(measureDurationMs(10, 5)).toBe(0);
    expect(measureDurationMs(10, Number.NaN)).toBe(0);
  });
});
