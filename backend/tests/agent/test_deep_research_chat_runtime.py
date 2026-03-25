from __future__ import annotations

from dataclasses import dataclass

from backend.agent.chat_history.idempotency import InMemoryChatIdempotencyStore
from backend.agent.chat_history.store import InMemoryChatTranscriptStore
from backend.agent.deep_research_chat_runtime import DeepResearchChatRuntime
from backend.agent.deep_research.coordinator import DeepResearchCoordinatorAnswer


@dataclass
class StubCoordinator:
    final_answer: str

    def respond(self, *, thread_id: str, history: list[object], latest_user_message: str) -> DeepResearchCoordinatorAnswer:
        del thread_id, history, latest_user_message
        return DeepResearchCoordinatorAnswer(text=self.final_answer, sources=[])


def test_deep_research_chat_runtime_appends_only_final_assistant_message() -> None:
    transcript_store = InMemoryChatTranscriptStore()
    thread = transcript_store.create_thread(mode="deep_research")
    runtime = DeepResearchChatRuntime(
        transcript_store=transcript_store,
        coordinator=StubCoordinator(
            final_answer="Need one more detail before I decompose the research."
        ),
        idempotency_store=InMemoryChatIdempotencyStore(),
    )

    response = runtime.post_message(
        thread_id=thread.thread_id,
        content="Research the vendor landscape",
        idempotency_key="msg-1",
    )

    assert response.assistant_message.content.startswith("Need one more detail")
    assert len(response.visible_messages) == 2
