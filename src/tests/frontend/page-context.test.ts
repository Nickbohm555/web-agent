import { describe, expect, it } from "vitest";

import { resolvePageContext } from "../../frontend/client/page-context.js";

describe("page context", () => {
  it("maps the launcher root to quick search", () => {
    expect(resolvePageContext("/")).toMatchObject({
      mode: "quick",
      pageTitle: "Quick search",
    });
  });

  it("maps agentic thread routes to the agentic page", () => {
    expect(resolvePageContext("/agentic/thread-123")).toMatchObject({
      mode: "agentic",
      pageTitle: "Agentic search",
      threadId: "thread-123",
    });
  });

  it("treats removed deep-research routes as the quick launcher", () => {
    expect(resolvePageContext("/deep-research/thread-456")).toMatchObject({
      mode: "quick",
      pageTitle: "Quick search",
      threadId: null,
    });
  });
});
