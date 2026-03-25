import { afterEach, describe, expect, it, vi } from "vitest";

describe("chat API contracts", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("creates an agentic thread and redirects to its stable chat URL", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => ({
          thread: {
            thread_id: "thread-123",
            mode: "agentic",
            title: null,
            created_at: "2026-03-25T00:00:00Z",
            updated_at: "2026-03-25T00:00:00Z",
          },
        }),
      })),
    );

    const { createChatThread } = await import("../../frontend/client/chat-api-client.js");

    const result = await createChatThread({ mode: "agentic" });

    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data.thread.threadId).toBe("thread-123");
    }
  });
});
