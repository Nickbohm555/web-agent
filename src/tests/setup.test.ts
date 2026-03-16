import { describe, expect, it } from "vitest";

import {
  FetchRequestSchema,
  FetchResponseSchema,
  SearchRequestSchema,
  SearchResponseSchema,
  fetch,
  normalizeFetchRequest,
  normalizeSearchRequest,
} from "../sdk/index.js";

describe("sdk foundation", () => {
  it("exports stable search and fetch entry points", async () => {
    const sdk = await import("../sdk/index.js");

    expect(typeof sdk.search).toBe("function");
    expect(typeof sdk.fetch).toBe("function");
    expect(fetch).toBe(sdk.fetch);
  });

  it("rejects malformed contract inputs", () => {
    expect(() =>
      SearchRequestSchema.parse({
        query: "   ",
        options: {
          limit: 0,
        },
      }),
    ).toThrow();

    expect(() =>
      FetchRequestSchema.parse({
        url: "not-a-url",
      }),
    ).toThrow();

    expect(() =>
      SearchResponseSchema.parse({
        query: "q",
        results: [
          {
            title: "",
            url: "https://example.com",
            snippet: "",
            rank: {
              position: 1,
            },
          },
        ],
        metadata: {
          resultCount: 1,
        },
      }),
    ).toThrow();

    expect(() =>
      FetchResponseSchema.parse({
        url: "https://example.com",
        text: "",
        markdown: "",
        metadata: {
          finalUrl: "https://example.com",
          contentType: null,
          statusCode: 99,
        },
        fallbackReason: null,
      }),
    ).toThrow();
  });

  it("normalizes equivalent search and fetch inputs to canonical defaults", () => {
    expect(
      normalizeSearchRequest("  Baseline Query  ", {
        limit: "10",
        country: "us",
        language: "EN",
      }),
    ).toEqual(
      normalizeSearchRequest("Baseline Query", {
        limit: 10,
        country: "US",
        language: "en",
      }),
    );

    expect(
      normalizeSearchRequest("Baseline Query"),
    ).toEqual({
      query: "Baseline Query",
      options: {
        maxResults: 10,
        timeoutMs: 5000,
        country: "US",
        language: "en",
        freshness: "any",
      },
    });

    expect(
      normalizeFetchRequest("https://example.com/path#section", {
        timeoutMs: "10000",
      }),
    ).toEqual(
      normalizeFetchRequest("https://example.com/path", {
        timeoutMs: 10000,
      }),
    );
  });
});
