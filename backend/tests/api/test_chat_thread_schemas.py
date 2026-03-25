from __future__ import annotations

from backend.api.schemas.chat.message import ChatThreadSummary
from backend.api.schemas.chat.thread import CreateChatThreadResponse


def test_create_thread_response_contract() -> None:
    payload = CreateChatThreadResponse(
        thread=ChatThreadSummary(
            thread_id="thread-123",
            mode="agentic",
            title=None,
            created_at="2026-03-25T00:00:00Z",
            updated_at="2026-03-25T00:00:00Z",
        )
    )

    assert payload.model_dump(mode="json")["thread"]["mode"] == "agentic"
