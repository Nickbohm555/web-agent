from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol
from uuid import uuid4

from backend.agent.chat_history.models import (
    ChatMessageRecord,
    ChatMessageRole,
    ChatThreadRecord,
)
from backend.agent.schemas import AgentRunMode, AgentSourceReference


class ChatTranscriptStore(Protocol):
    def create_thread(self, *, mode: AgentRunMode) -> ChatThreadRecord: ...

    def append_message(
        self,
        *,
        thread_id: str,
        role: ChatMessageRole,
        content: str,
        sources: list[AgentSourceReference] | None = None,
    ) -> ChatMessageRecord: ...

    def get_thread(self, thread_id: str) -> ChatThreadRecord: ...


class InMemoryChatTranscriptStore:
    def __init__(self) -> None:
        self._threads: dict[str, ChatThreadRecord] = {}

    def create_thread(self, *, mode: AgentRunMode) -> ChatThreadRecord:
        created_at = _timestamp()
        thread = ChatThreadRecord(
            thread_id=f"thread-{uuid4()}",
            mode=mode,
            created_at=created_at,
            updated_at=created_at,
        )
        self._threads[thread.thread_id] = thread
        return thread

    def append_message(
        self,
        *,
        thread_id: str,
        role: ChatMessageRole,
        content: str,
        sources: list[AgentSourceReference] | None = None,
    ) -> ChatMessageRecord:
        thread = self.get_thread(thread_id)
        message = ChatMessageRecord(
            message_id=f"msg-{uuid4()}",
            thread_id=thread_id,
            role=role,
            content=content,
            created_at=_timestamp(),
            sources=sources,
        )
        thread.messages.append(message)
        thread.updated_at = message.created_at
        return message

    def get_thread(self, thread_id: str) -> ChatThreadRecord:
        try:
            return self._threads[thread_id]
        except KeyError as exc:
            raise KeyError(f"Unknown chat thread: {thread_id}") from exc


def _timestamp() -> str:
    return datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")
