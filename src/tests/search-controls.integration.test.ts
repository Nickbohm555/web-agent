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

  it("uses deterministic locale defaults and omits freshness mapping when not set", async () => {
    const { search } = await import("../sdk/index.js");

    requestMock.mockResolvedValueOnce(
      createResponse(200, {
        organic: [{ title: "One", link: "https://example.com/1" }],
      }),
    );

    await search("agents");

    expect(getRequestBody(0)).toEqual({
      q: "agents",
      num: 10,
      gl: "us",
      hl: "en",
    });
  });

  it("maps each freshness control to a stable Serper request value", async () => {
    const { search } = await import("../sdk/index.js");

    const freshnessCases = [
      { freshness: "day", tbs: "qdr:d" },
      { freshness: "week", tbs: "qdr:w" },
      { freshness: "month", tbs: "qdr:m" },
      { freshness: "year", tbs: "qdr:y" },
    ] as const;

    for (const testCase of freshnessCases) {
      requestMock.mockResolvedValueOnce(
        createResponse(200, {
          organic: [{ title: `${testCase.freshness}`, link: `https://example.com/${testCase.freshness}` }],
        }),
      );

      await search("agents", { freshness: testCase.freshness });
    }

    expect(requestMock).toHaveBeenCalledTimes(freshnessCases.length);

    freshnessCases.forEach((testCase, index) => {
      expect(getRequestBody(index)).toEqual(
        expect.objectContaining({
          q: "agents",
          tbs: testCase.tbs,
        }),
      );
    });
  });

  it("rejects when the provider call exceeds the configured timeout budget", async () => {
    const { search } = await import("../sdk/index.js");

    requestMock.mockImplementationOnce((_url, options) =>
      new Promise((_resolve, reject) => {
        options.signal.addEventListener(
          "abort",
          () => reject(options.signal.reason),
          { once: true },
        );
      }),
    );

    await expect(
      search("agents", {
        timeoutMs: 250,
      }),
    ).rejects.toSatisfy((error) => error instanceof DOMException && error.name === "TimeoutError");
  });

  it("enforces mixed include and exclude precedence on final normalized results", async () => {
    const { search } = await import("../sdk/index.js");

    requestMock.mockResolvedValueOnce(
      createResponse(200, {
        organic: [
          { title: "Blocked", link: "https://blocked.com/post", position: 1 },
          { title: "Allowed", link: "https://docs.example.com/page", position: 2 },
          { title: "Ignored", link: "https://another.dev/post", position: 3 },
        ],
      }),
    );

    await expect(
      search("agents", {
        maxResults: 1,
        includeDomains: ["example.com", "blocked.com"],
        excludeDomains: ["blocked.com"],
        country: "CA",
        language: "FR",
        freshness: "month",
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
            providerPosition: 2,
          },
        },
      ],
      metadata: {
        resultCount: 1,
      },
    });

    expect(getRequestBody(0)).toEqual({
      q: "agents site:example.com -site:blocked.com",
      num: 1,
      gl: "ca",
      hl: "fr",
      tbs: "qdr:m",
    });
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

function getRequestBody(index: number): Record<string, unknown> {
  const body = requestMock.mock.calls[index]?.[1]?.body;

  if (typeof body !== "string") {
    throw new Error(`Expected request body string at call ${index}`);
  }

  return JSON.parse(body) as Record<string, unknown>;
}
