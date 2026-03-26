import { describe, expect, it, vi } from "vitest";

describe("backend agent executor", () => {
  it("forwards thread ids to the backend agent route for conversational modes", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            run_id: "backend-agentic-run",
            status: "completed",
            final_answer: {
              text: "Agentic answer.",
              citations: [],
              basis: [],
            },
            sources: [],
            tool_call_count: 2,
            elapsed_ms: 120,
            metadata: {
              tool_call_count: 2,
              elapsed_ms: 120,
            },
          }),
          {
            status: 200,
            headers: {
              "content-type": "application/json",
            },
          },
        ),
      );

    const { createHttpAgentRunExecutor } = await import("../../frontend/routes/backend-agent.js");
    const executor = createHttpAgentRunExecutor("http://backend.example", fetchMock);

    await executor({
      prompt: "Continue the prior research thread.",
      mode: "agentic",
      runId: "frontend-run",
      threadId: "thread-agentic-123",
      signal: new AbortController().signal,
    });

    expect(fetchMock).toHaveBeenCalledWith(
      new URL("/api/agent/run", "http://backend.example"),
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          prompt: "Continue the prior research thread.",
          mode: "agentic",
          thread_id: "thread-agentic-123",
        }),
      }),
    );
  });
});
