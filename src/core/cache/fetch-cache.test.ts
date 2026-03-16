import { describe, expect, it } from "vitest";

import {
  createFetchCache,
  createFetchCacheKey,
} from "./fetch-cache.js";
import { normalizeFetchRequest, type FetchResponse } from "../../sdk/contracts/fetch.js";

describe("fetch cache", () => {
  it("uses normalized fetch requests for stable cache keying", () => {
    const withHash = normalizeFetchRequest("https://example.com/article#intro", {
      timeoutMs: 1_000,
      maxAgeMs: 500,
      fresh: true,
    });
    const canonical = normalizeFetchRequest("https://example.com/article", {
      timeoutMs: 5_000,
      maxAgeMs: 60_000,
      fresh: false,
    });

    expect(createFetchCacheKey(withHash)).toBe(createFetchCacheKey(canonical));
  });

  it("returns a hit when an entry is within the requested maxAge", () => {
    let now = 10_000;
    const cache = createFetchCache({ now: () => now });
    const request = normalizeFetchRequest("https://example.com/article");

    cache.write(request, createResponse("cached"));
    now = 10_250;

    const result = cache.read(request, {
      mode: "eligible",
      maxAgeMs: 500,
    });

    expect(result).toMatchObject({
      kind: "hit",
      ageMs: 250,
      entry: {
        key: "https://example.com/article",
      },
    });
    expect(result.kind === "hit" ? result.entry.response.text : "").toBe("cached");
  });

  it("returns a stale miss when an entry exceeds maxAge", () => {
    let now = 1_000;
    const cache = createFetchCache({ now: () => now });
    const request = normalizeFetchRequest("https://example.com/article");

    cache.write(request, createResponse("old"));
    now = 2_500;

    const result = cache.read(request, {
      mode: "eligible",
      maxAgeMs: 1_000,
    });

    expect(result).toMatchObject({
      kind: "stale",
      ageMs: 1_500,
    });
    expect(result.kind === "stale" ? result.entry?.response.text : "").toBe("old");
  });

  it("bypasses cache reads when force-fresh is requested", () => {
    const cache = createFetchCache();
    const request = normalizeFetchRequest("https://example.com/article");

    cache.write(request, createResponse("cached"));

    expect(
      cache.read(request, {
        mode: "bypass",
        maxAgeMs: 60_000,
      }),
    ).toEqual({
      kind: "bypass",
    });
  });

  it("writes fetched responses for later non-fresh reads", () => {
    let now = 500;
    const cache = createFetchCache({ now: () => now });
    const request = normalizeFetchRequest("https://example.com/article", {
      fresh: true,
    });

    cache.write(request, createResponse("fresh result"));
    now = 700;

    const result = cache.read(
      normalizeFetchRequest("https://example.com/article"),
      {
        mode: "eligible",
        maxAgeMs: 1_000,
      },
    );

    expect(result.kind).toBe("hit");
    expect(result.kind === "hit" ? result.entry.response.text : "").toBe("fresh result");
  });
});

function createResponse(text: string): FetchResponse {
  return {
    url: "https://example.com/article",
    text,
    markdown: text,
    meta: {
      operation: "fetch",
      durationMs: 5,
      attempts: 1,
      retries: 0,
      cacheHit: false,
      timings: {
        networkMs: 5,
      },
    },
    metadata: {
      finalUrl: "https://example.com/article",
      contentType: "text/html",
      statusCode: 200,
    },
    fallbackReason: null,
  };
}
