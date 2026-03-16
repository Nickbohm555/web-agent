import { describe, expect, it } from "vitest";

import { fetch, search } from "../sdk/index.js";

describe("sdk foundation", () => {
  it("exports stable search and fetch entry points", async () => {
    await expect(search("baseline query")).resolves.toEqual({
      query: "baseline query",
      results: [],
    });

    await expect(fetch("https://example.com")).resolves.toEqual({
      url: "https://example.com",
      content: "",
    });
  });
});
