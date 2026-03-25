from __future__ import annotations

from backend.api.schemas.chat.message import ChatMessage


def last_assistant_message(history: list[ChatMessage]) -> ChatMessage | None:
    for message in reversed(history):
        if message.role == "assistant":
            return message
    return None
