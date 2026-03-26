from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from backend.agent.schemas import AgentRunMode, AgentSourceReference


ChatMessageRole = Literal["user", "assistant"]


@dataclass
class ChatMessageRecord:
    message_id: str
    thread_id: str
    role: ChatMessageRole
    content: str
    created_at: str
    sources: list[AgentSourceReference] | None = None


@dataclass
class ChatThreadRecord:
    thread_id: str
    mode: AgentRunMode
    created_at: str
    updated_at: str
    title: str | None = None
    messages: list[ChatMessageRecord] = field(default_factory=list)
