from __future__ import annotations

from typing import Protocol

from backend.agent.chat_history.idempotency import ChatIdempotencyStore
from backend.agent.chat_history.store import ChatTranscriptStore
from backend.agent.schemas import AgentRunMode, AgentRunResult
from backend.api.schemas.chat.post_message import PostChatMessageResponse


class AgenticRunner(Protocol):
    def __call__(self, prompt: str, mode: AgentRunMode = "agentic", **kwargs: object) -> AgentRunResult: ...


class AgenticChatRuntime:
    def __init__(
        self,
        *,
        transcript_store: ChatTranscriptStore,
        agent_runner: AgenticRunner,
        idempotency_store: ChatIdempotencyStore,
    ) -> None:
        self._transcript_store = transcript_store
        self._agent_runner = agent_runner
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

        user_message = self._transcript_store.append_message(
            thread_id=thread_id,
            role="user",
            content=content,
        )
        result = self._agent_runner(content, "agentic")
        if result.final_answer is None:
            raise ValueError("agentic chat runtime requires a completed final answer")
        assistant_message = self._transcript_store.append_message(
            thread_id=thread_id,
            role="assistant",
            content=result.final_answer.text,
            sources=result.sources,
        )
        thread = self._transcript_store.get_thread(thread_id)
        return reservation.store_result(
            thread=thread,
            user_message=user_message,
            assistant_message=assistant_message,
        )
