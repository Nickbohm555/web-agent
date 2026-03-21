from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from .tool_errors import ToolMeta


class WebSearchInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    query: str = Field(min_length=1)
    max_results: int = Field(default=5, ge=1, le=10)

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("query must not be blank")
        return normalized


class SearchRank(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    position: int = Field(ge=1)
    provider_position: Optional[int] = Field(default=None, ge=1)
    rerank_score: Optional[float] = Field(default=None, ge=0)


class WebSearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    title: str = Field(min_length=1)
    url: HttpUrl
    snippet: str
    rank: SearchRank

    @field_validator("title", "snippet")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def validate_title(self) -> "WebSearchResult":
        if not self.title:
            raise ValueError("title must not be blank")
        return self

    def to_source_record(self) -> dict[str, str]:
        return {
            "title": self.title,
            "url": str(self.url),
            "snippet": self.snippet,
        }


class SearchMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    result_count: int = Field(ge=0)
    provider: str = Field(min_length=1)


class WebSearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    query: str = Field(min_length=1)
    results: List[WebSearchResult]
    metadata: SearchMetadata
    meta: ToolMeta

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("query must not be blank")
        return normalized

    @model_validator(mode="after")
    def validate_result_count(self) -> "WebSearchResponse":
        if self.metadata.result_count != len(self.results):
            raise ValueError("metadata.result_count must match results length")
        return self
