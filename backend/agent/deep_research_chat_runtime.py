from __future__ import annotations

from typing import Protocol

from backend.agent.chat_history.idempotency import ChatIdempotencyStore
from backend.agent.chat_history.store import ChatTranscriptStore
from backend.agent.deep_research.coordinator import DeepResearchCoordinatorAnswer
from backend.api.schemas.chat.message import ChatMessage
from backend.api.schemas.chat.post_message import PostChatMessageResponse


class DeepResearchCoordinator(Protocol):
    def respond(
        self,
        *,
        thread_id: str,
        history: list[ChatMessage],
        latest_user_message: str,
    ) -> DeepResearchCoordinatorAnswer: ...


class DeepResearchChatRuntime:
    def __init__(
        self,
        *,
        transcript_store: ChatTranscriptStore,
        coordinator: DeepResearchCoordinator,
        idempotency_store: ChatIdempotencyStore,
    ) -> None:
        self._transcript_store = transcript_store
        self._coordinator = coordinator
        self._idempotency_store = idempotency_store

    def post_message(
        self,
        *,
        thread_id: str,
        content: str,
        idempotency_key: str,
    ) -> PostChatMessageResponse:
        reservation = self._idempotency_store.reserve(thread_id, idempotency_key)
        if reservation.cached_response is not None:
            return reservation.cached_response

        existing_thread = self._transcript_store.get_thread(thread_id)
        history = [
            ChatMessage.model_validate(message, from_attributes=True)
            for message in existing_thread.messages
        ]
        user_message = self._transcript_store.append_message(
            thread_id=thread_id,
            role="user",
            content=content,
        )
        answer = self._coordinator.respond(
            thread_id=thread_id,
            history=history,
            latest_user_message=content,
        )
        assistant_message = self._transcript_store.append_message(
            thread_id=thread_id,
            role="assistant",
            content=answer.text,
            sources=answer.sources,
        )
        thread = self._transcript_store.get_thread(thread_id)
        return reservation.store_result(
            thread=thread,
            user_message=user_message,
            assistant_message=assistant_message,
        )
