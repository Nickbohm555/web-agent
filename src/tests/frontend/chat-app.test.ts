import { describe, expect, it } from "vitest";

import { buildChatPageModel } from "../../frontend/client/chat-app.js";

describe("chat app route bootstrap", () => {
  it("builds a transcript-first agentic chat page model from the stable route", () => {
    expect(buildChatPageModel("/agentic/thread-123")).toEqual({
      mode: "agentic",
      threadId: "thread-123",
      heading: "Agentic thread",
      postUrl: "/api/chat/threads/thread-123/messages",
    });
  });
});
