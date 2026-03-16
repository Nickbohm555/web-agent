import { beforeEach, describe, expect, it, vi } from "vitest";

const requestMock = vi.fn();

vi.mock("undici", () => ({
  request: requestMock,
}));

describe("search metadata", () => {
  beforeEach(() => {
    requestMock.mockReset();
    vi.resetModules();
    process.env.SERPER_API_KEY = "test-key";
  });

  it("emits stable inspectable call metadata on successful search responses", async () => {
    const { search } = await import("../../sdk/index.js");

    requestMock.mockResolvedValueOnce(
      createResponse(200, {
        organic: [
          { title: "One", link: "https://example.com/1", snippet: "First" },
          { title: "Two", link: "https://example.com/2", snippet: "Second" },
        ],
      }),
    );

    const response = await search("agents", {
      maxResults: 1,
      country: "US",
      language: "EN",
    });

    expect(response).toMatchObject({
      query: "agents",
      results: [
        {
          title: "One",
          url: "https://example.com/1",
          snippet: "First",
          rank: {
            position: 1,
            providerPosition: 1,
          },
        },
      ],
      meta: {
        operation: "search",
        attempts: 1,
        retries: 0,
        cacheHit: false,
        usage: {
          provider: {
            organicResults: 2,
          },
        },
      },
      metadata: {
        resultCount: 1,
      },
    });

    expect(response.meta.durationMs).toBeGreaterThanOrEqual(0);
    expect(response.meta.timings.providerMs).toBeGreaterThanOrEqual(0);
    expect(response.meta.timings.mappingMs).toBeGreaterThanOrEqual(0);
  });

  it("keeps provider metadata programmatically inspectable without leaking raw provider payloads", async () => {
    const { search } = await import("../../sdk/index.js");

    requestMock.mockResolvedValueOnce(
      createResponse(200, {
        organic: [
          {
            title: "Visible Result",
            link: "https://example.com/visible",
            snippet: "Snippet",
            credits: 99,
            sitelinks: [{ title: "Hidden child" }],
          },
        ],
        credits: 123,
      }),
    );

    const response = await search("agents");

    expect(response.meta.usage?.provider?.organicResults).toBe(1);
    expect(Object.keys(response.meta.timings).sort()).toEqual(["mappingMs", "providerMs"]);
    expect(response.results[0]).toEqual({
      title: "Visible Result",
      url: "https://example.com/visible",
      snippet: "Snippet",
      rank: {
        position: 1,
        providerPosition: 1,
      },
    });
    expect(response.results[0]).not.toHaveProperty("credits");
    expect(response.results[0]).not.toHaveProperty("sitelinks");
    expect(response).not.toHaveProperty("organic");
  });
});

function createResponse(
  statusCode: number,
  payload: unknown,
  headers?: Record<string, string>,
) {
  return {
    statusCode,
    headers,
    body: {
      json: vi.fn().mockResolvedValue(payload),
    },
  };
}
