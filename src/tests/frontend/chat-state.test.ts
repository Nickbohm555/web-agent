import { describe, expect, it } from "vitest";

import {
  initialChatState,
  reduceChatState,
} from "../../frontend/client/chat-state.js";

describe("chat state reducer", () => {
  it("appends returned assistant messages without rebuilding history from run events", () => {
    const state = reduceChatState(initialChatState, {
      type: "message_posted",
      response: {
        thread: {
          threadId: "thread-123",
          mode: "agentic",
          title: null,
          createdAt: "2026-03-25T00:00:00Z",
          updatedAt: "2026-03-25T00:00:02Z",
        },
        userMessage: {
          messageId: "u1",
          threadId: "thread-123",
          role: "user",
          content: "Find updates",
          createdAt: "2026-03-25T00:00:01Z",
          sources: null,
        },
        assistantMessage: {
          messageId: "a1",
          threadId: "thread-123",
          role: "assistant",
          content: "Here are updates",
          createdAt: "2026-03-25T00:00:02Z",
          sources: null,
        },
        visibleMessages: [],
      },
    });

    expect(state.messages.map((message) => message.role)).toEqual(["user", "assistant"]);
  });
});
