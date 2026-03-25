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

  it("maps deep-research thread routes to the deep-research page", () => {
    expect(resolvePageContext("/deep-research/thread-456")).toMatchObject({
      mode: "deep_research",
      pageTitle: "Deep research",
      threadId: "thread-456",
    });
  });
});
