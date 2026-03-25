from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from backend.api.schemas.chat.message import ChatMessage, ChatThreadSummary
from backend.api.schemas.chat.post_message import PostChatMessageResponse


class ChatIdempotencyStore(Protocol):
    def reserve(self, thread_id: str, idempotency_key: str) -> "ChatIdempotencyReservation": ...


@dataclass
class ChatIdempotencyReservation:
    thread_id: str
    idempotency_key: str
    _responses: dict[tuple[str, str], PostChatMessageResponse]
    cached_response: PostChatMessageResponse | None = None

    def store_result(
        self,
        *,
        thread: object,
        user_message: object,
        assistant_message: object,
    ) -> PostChatMessageResponse:
        thread_payload = ChatThreadSummary.model_validate(thread, from_attributes=True)
        user_payload = ChatMessage.model_validate(user_message, from_attributes=True)
        assistant_payload = ChatMessage.model_validate(
            assistant_message,
            from_attributes=True,
        )
        response = PostChatMessageResponse(
            thread=thread_payload,
            user_message=user_payload,
            assistant_message=assistant_payload,
            visible_messages=[user_payload, assistant_payload],
        )
        self._responses[(self.thread_id, self.idempotency_key)] = response
        self.cached_response = response
        return response


class InMemoryChatIdempotencyStore:
    def __init__(self) -> None:
        self._responses: dict[tuple[str, str], PostChatMessageResponse] = {}

    def reserve(self, thread_id: str, idempotency_key: str) -> ChatIdempotencyReservation:
        return ChatIdempotencyReservation(
            thread_id=thread_id,
            idempotency_key=idempotency_key,
            _responses=self._responses,
            cached_response=self._responses.get((thread_id, idempotency_key)),
        )
