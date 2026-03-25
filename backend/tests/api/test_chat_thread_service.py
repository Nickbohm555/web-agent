from __future__ import annotations

from backend.agent.chat_history.store import InMemoryChatTranscriptStore
from backend.api.services.chat_threads import ChatThreadService


def test_chat_thread_service_persists_user_and_assistant_messages() -> None:
    store = InMemoryChatTranscriptStore()
    service = ChatThreadService(transcript_store=store)

    thread = service.create_thread(mode="agentic")
    service.append_message(thread.thread_id, role="user", content="Find sources")
    service.append_message(thread.thread_id, role="assistant", content="Here are sources")

    transcript = service.get_thread(thread.thread_id)
    assert [message.role for message in transcript.messages] == ["user", "assistant"]
