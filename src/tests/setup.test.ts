import { describe, expect, it } from "vitest";

import {
  FetchRequestSchema,
  FetchResponseSchema,
  SearchRequestSchema,
  SearchResponseSchema,
  fetch,
  normalizeFetchRequest,
  normalizeSearchRequest,
  search,
} from "../sdk/index.js";

describe("sdk foundation", () => {
  it("exports stable search and fetch entry points", async () => {
    await expect(search("baseline query")).resolves.toEqual({
      query: "baseline query",
      results: [],
      metadata: {
        resultCount: 0,
      },
    });

    await expect(fetch("https://example.com")).resolves.toEqual({
      url: "https://example.com/",
      text: "",
      markdown: "",
      metadata: {
        finalUrl: "https://example.com/",
        contentType: null,
        statusCode: null,
      },
      fallbackReason: null,
    });
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
        limit: 10,
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
