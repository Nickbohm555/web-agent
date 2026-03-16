import { readFileSync } from "node:fs";

import { describe, expect, it } from "vitest";

import { mapSerperOrganicToSearchResponse } from "../../providers/serper/mapper.js";
import type { SerperSearchResponse } from "../../providers/serper/client.js";

describe("Serper mapper", () => {
  it("maps organic results into the normalized search contract deterministically", () => {
    const payload = loadFixture();

    const mapped = mapSerperOrganicToSearchResponse(payload, {
      query: "Example Query",
      limit: 10,
    });

    expect(mapped).toEqual({
      query: "Example Query",
      results: [
        {
          title: "Example Domain",
          url: "https://example.com/",
          snippet: "Example snippet for the first result.",
          rank: {
            position: 1,
            providerPosition: 3,
          },
        },
        {
          title: "Second Result",
          url: "https://example.org/docs",
          snippet: "",
          rank: {
            position: 2,
            providerPosition: 4,
          },
        },
        {
          title: "Third Result",
          url: "https://example.net/path?x=1#fragment",
          snippet: "Third snippet",
          rank: {
            position: 3,
            providerPosition: 5,
          },
        },
      ],
      metadata: {
        resultCount: 3,
      },
    });
  });

  it("produces identical output for equivalent provider payloads across repeated runs", () => {
    const payload = loadFixture();
    const equivalentPayload: SerperSearchResponse = {
      organic: payload.organic.map((entry) => ({
        ...entry,
        title: typeof entry.title === "string" ? ` ${entry.title.trim()} ` : entry.title,
        link: typeof entry.link === "string" ? ` ${entry.link.trim()} ` : entry.link,
        snippet: typeof entry.snippet === "string" ? ` ${entry.snippet.trim()} ` : entry.snippet,
      })),
    };

    const first = mapSerperOrganicToSearchResponse(payload, {
      query: "Equivalent Query",
      limit: 2,
    });
    const second = mapSerperOrganicToSearchResponse(payload, {
      query: "Equivalent Query",
      limit: 2,
    });
    const third = mapSerperOrganicToSearchResponse(equivalentPayload, {
      query: "Equivalent Query",
      limit: 2,
    });

    expect(second).toEqual(first);
    expect(third).toEqual(first);
  });
});

function loadFixture(): SerperSearchResponse {
  const fixturePath = new URL("../fixtures/serper/organic.json", import.meta.url);
  return JSON.parse(readFileSync(fixturePath, "utf8")) as SerperSearchResponse;
}
