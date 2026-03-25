from __future__ import annotations

from backend.agent.agentic_chat_runtime import AgenticChatRuntime
from backend.agent.chat_history.idempotency import InMemoryChatIdempotencyStore
from backend.agent.chat_history.store import InMemoryChatTranscriptStore
from backend.agent.schemas import AgentRunResult


def test_agentic_chat_runtime_appends_visible_transcript_messages() -> None:
    transcript_store = InMemoryChatTranscriptStore()
    thread = transcript_store.create_thread(mode="agentic")
    runtime = AgenticChatRuntime(
        transcript_store=transcript_store,
        agent_runner=lambda prompt, mode: AgentRunResult(
            run_id="run-1",
            status="completed",
            final_answer="Answer with sources.",
            sources=[],
            tool_call_count=1,
            elapsed_ms=12,
        ),
        idempotency_store=InMemoryChatIdempotencyStore(),
    )

    response = runtime.post_message(
        thread_id=thread.thread_id,
        content="Find recent updates",
        idempotency_key="msg-1",
    )

    assert response.user_message.role == "user"
    assert response.assistant_message.role == "assistant"
    assert [message.role for message in response.visible_messages] == ["user", "assistant"]
