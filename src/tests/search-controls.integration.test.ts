import { beforeEach, describe, expect, it, vi } from "vitest";

const requestMock = vi.fn();

vi.mock("undici", () => ({
  request: requestMock,
}));

describe("search controls integration", () => {
  beforeEach(() => {
    requestMock.mockReset();
    vi.resetModules();
    process.env.SERPER_API_KEY = "test-key";
  });

  it("maps normalized controls into the Serper request and filters out-of-scope results", async () => {
    const { search } = await import("../sdk/index.js");

    requestMock.mockResolvedValueOnce(
      createResponse(200, {
        organic: [
          { title: "Allowed", link: "https://docs.example.com/page", position: 4 },
          { title: "Blocked", link: "https://blocked.com/post", position: 1 },
          { title: "Other", link: "https://another.dev/post", position: 2 },
        ],
      }),
    );

    await expect(
      search("agents", {
        maxResults: 2,
        includeDomains: ["example.com"],
        excludeDomains: ["blocked.com"],
        freshness: "week",
        country: "US",
        language: "EN",
      }),
    ).resolves.toEqual({
      query: "agents",
      results: [
        {
          title: "Allowed",
          url: "https://docs.example.com/page",
          snippet: "",
          rank: {
            position: 1,
            providerPosition: 4,
          },
        },
      ],
      metadata: {
        resultCount: 1,
      },
    });

    expect(requestMock).toHaveBeenCalledWith(
      "https://google.serper.dev/search",
      expect.objectContaining({
        body: JSON.stringify({
          q: "agents site:example.com -site:blocked.com",
          num: 2,
          gl: "us",
          hl: "en",
          tbs: "qdr:w",
        }),
      }),
    );
  });

  it("passes timeout control as an abort signal and caps final results", async () => {
    const { search } = await import("../sdk/index.js");

    requestMock.mockResolvedValueOnce(
      createResponse(200, {
        organic: [
          { title: "One", link: "https://example.com/1" },
          { title: "Two", link: "https://example.com/2" },
          { title: "Three", link: "https://example.com/3" },
        ],
      }),
    );

    const response = await search("agents", {
      maxResults: 2,
      timeoutMs: 750,
    });

    expect(response.results).toHaveLength(2);
    expect(requestMock).toHaveBeenCalledTimes(1);

    const requestOptions = requestMock.mock.calls[0]?.[1];
    expect(requestOptions).toEqual(
      expect.objectContaining({
        signal: expect.any(AbortSignal),
      }),
    );
    expect(requestOptions.signal.aborted).toBe(false);
  });
});

function createResponse(statusCode: number, payload: unknown) {
  return {
    statusCode,
    body: {
      json: vi.fn().mockResolvedValue(payload),
    },
  };
}
