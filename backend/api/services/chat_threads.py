from __future__ import annotations

from backend.agent.agentic_chat_runtime import AgenticChatRuntime
from backend.agent.chat_history.store import ChatTranscriptStore
from backend.agent.schemas import AgentRunMode, AgentSourceReference
from backend.api.schemas.chat.message import ChatMessage, ChatThreadSummary
from backend.api.schemas.chat.post_message import PostChatMessageResponse
from backend.api.schemas.chat.thread import GetChatThreadResponse


class ChatThreadNotFoundError(KeyError):
    pass


class ChatThreadService:
    def __init__(
        self,
        transcript_store: ChatTranscriptStore,
        *,
        agentic_runtime: AgenticChatRuntime | None = None,
    ) -> None:
        self._transcript_store = transcript_store
        self._agentic_runtime = agentic_runtime

    def create_thread(self, mode: AgentRunMode) -> ChatThreadSummary:
        return _to_thread_summary(self._transcript_store.create_thread(mode=mode))

    def append_message(
        self,
        thread_id: str,
        *,
        role: str,
        content: str,
        sources: list[AgentSourceReference] | None = None,
    ) -> ChatMessage:
        return _to_chat_message(
            self._transcript_store.append_message(
                thread_id=thread_id,
                role=role,
                content=content,
                sources=sources,
            )
        )

    def get_thread(self, thread_id: str) -> GetChatThreadResponse:
        thread = self._get_thread_record(thread_id)
        return GetChatThreadResponse(
            thread=_to_thread_summary(thread),
            messages=[_to_chat_message(message) for message in thread.messages],
        )

    def post_message(
        self,
        thread_id: str,
        *,
        content: str,
        idempotency_key: str,
    ) -> PostChatMessageResponse:
        thread = self._get_thread_record(thread_id)
        if thread.mode == "agentic":
            if self._agentic_runtime is None:
                raise RuntimeError("Agentic chat runtime is not configured")
            return self._agentic_runtime.post_message(
                thread_id=thread_id,
                content=content,
                idempotency_key=idempotency_key,
            )

        user_message = self.append_message(thread_id, role="user", content=content)
        assistant_message = self.append_message(
            thread_id,
            role="assistant",
            content="Chat runtime not implemented yet.",
        )
        return PostChatMessageResponse(
            thread=_to_thread_summary(self._get_thread_record(thread_id)),
            user_message=user_message,
            assistant_message=assistant_message,
            visible_messages=[user_message, assistant_message],
        )

    def _get_thread_record(self, thread_id: str):
        try:
            return self._transcript_store.get_thread(thread_id)
        except KeyError as exc:
            raise ChatThreadNotFoundError(thread_id) from exc


def _to_thread_summary(thread: object) -> ChatThreadSummary:
    return ChatThreadSummary.model_validate(thread, from_attributes=True)


def _to_chat_message(message: object) -> ChatMessage:
    return ChatMessage.model_validate(message, from_attributes=True)
