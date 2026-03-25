from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.agent.schemas import AgentRunMode, AgentSourceReference


class ChatThreadSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    thread_id: str = Field(min_length=1)
    mode: AgentRunMode
    title: str | None = None
    created_at: str = Field(min_length=1)
    updated_at: str = Field(min_length=1)


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str = Field(min_length=1)
    thread_id: str = Field(min_length=1)
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)
    created_at: str = Field(min_length=1)
    sources: list[AgentSourceReference] | None = None
