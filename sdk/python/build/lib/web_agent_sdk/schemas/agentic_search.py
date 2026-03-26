from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class AgenticSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=1)
    mode: str = Field(default="agentic")
    thread_id: str | None = None


class AgenticSearchCitation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    url: HttpUrl
    start_index: int = Field(ge=0)
    end_index: int = Field(gt=0)


class AgenticSearchBasisItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: str = Field(min_length=1)
    text: str = Field(min_length=1)
    citations: list[AgenticSearchCitation] = Field(default_factory=list)


class AgenticSearchAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    citations: list[AgenticSearchCitation] = Field(default_factory=list)
    basis: list[AgenticSearchBasisItem] = Field(default_factory=list)


class AgenticSearchSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    url: HttpUrl
    snippet: str = ""


class AgenticSearchMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_call_count: int = Field(ge=0)
    elapsed_ms: int = Field(ge=0)


class AgenticSearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)
    status: str = Field(min_length=1)
    final_answer: AgenticSearchAnswer
    sources: list[AgenticSearchSource] = Field(default_factory=list)
    tool_call_count: int = Field(ge=0)
    elapsed_ms: int = Field(ge=0)
    metadata: AgenticSearchMetadata
