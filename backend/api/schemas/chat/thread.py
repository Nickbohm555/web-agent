from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from backend.agent.schemas import AgentRunMode
from backend.api.schemas.chat.message import ChatMessage, ChatThreadSummary


class CreateChatThreadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: AgentRunMode


class CreateChatThreadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    thread: ChatThreadSummary


class GetChatThreadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    thread: ChatThreadSummary
    messages: list[ChatMessage] = Field(default_factory=list)
