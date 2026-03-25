from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ChatErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)


class ChatErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: ChatErrorDetail
