import { describe, expect, it, vi } from "vitest";

describe("backend agent executor", () => {
  it("polls queued deep-research runs until a final answer is available", async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            run_id: "backend-deep-run",
            status: "queued",
            metadata: {
              execution_surface: "background",
            },
          }),
          {
            status: 202,
            headers: {
              "content-type": "application/json",
            },
          },
        ),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            run_id: "backend-deep-run",
            thread_id: "thread-backend-deep-run",
            status: "completed",
            final_answer: {
              text: "Deep answer.",
              citations: [],
              basis: [],
            },
            sources: [
              {
                source_id: "source-1",
                title: "Primary source",
                url: "https://example.com/source",
                snippet: "Evidence snippet.",
              },
            ],
            error: null,
            sub_questions: ["What changed?"],
            metadata: {
              execution_surface: "background",
              stage: "completed",
              wave_count: 1,
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
    const executor = createHttpAgentRunExecutor(
      "http://backend.example",
      fetchMock,
      async () => {},
    );

    const result = await executor({
      prompt: "Research OpenAI",
      mode: "deep_research",
      runId: "frontend-run",
      signal: new AbortController().signal,
    });

    expect(result).toEqual({
      status: "completed",
      finalAnswer: "Deep answer.",
      structuredAnswer: {
        text: "Deep answer.",
        citations: [],
        basis: [],
      },
      sources: [
        {
          source_id: "source-1",
          title: "Primary source",
          url: "https://example.com/source",
          snippet: "Evidence snippet.",
        },
      ],
      completedAt: expect.any(Number),
    });
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      new URL("/api/agent/run", "http://backend.example"),
      expect.objectContaining({
        method: "POST",
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      new URL("/api/agent/deep-research/backend-deep-run", "http://backend.example"),
      expect.objectContaining({
        method: "GET",
      }),
    );
  });

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
