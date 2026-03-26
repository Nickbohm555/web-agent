from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class AgenticSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1)


class AgenticSearchSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    url: HttpUrl


class AgenticSearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    model: str = Field(min_length=1)
    sources: list[AgenticSearchSource] = Field(default_factory=list)
