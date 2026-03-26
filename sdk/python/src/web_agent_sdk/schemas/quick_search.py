from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class QuickSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1)


class QuickSearchSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    url: HttpUrl


class QuickSearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    model: str = Field(min_length=1)
    sources: list[QuickSearchSource] = Field(default_factory=list)
