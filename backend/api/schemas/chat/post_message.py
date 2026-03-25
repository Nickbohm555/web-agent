from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from backend.api.schemas.chat.message import ChatMessage, ChatThreadSummary


class PostChatMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1)


class PostChatMessageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    thread: ChatThreadSummary
    user_message: ChatMessage
    assistant_message: ChatMessage
    visible_messages: list[ChatMessage] = Field(default_factory=list)
