from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator


AgentRunMode = Literal["quick", "agentic", "deep_research"]
AgentRunStatus = Literal["completed", "failed"]
AgentRuntimeExecutionMode = Literal["single_pass", "bounded_agent_loop", "background_research"]
AgentRunErrorCategory = Literal[
    "invalid_prompt",
    "loop_limit",
    "tool_failure",
    "provider_failure",
    "timeout",
    "internal_error",
]
AgentRetrievalFreshness = Literal["any", "day", "week", "month", "year"]


class AgentRunError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: AgentRunErrorCategory
    message: str = Field(min_length=1)
    retryable: bool


class AgentRunRetrievalSearchPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    country: str = Field(default="US", min_length=1)
    language: str = Field(default="en", min_length=1)
    freshness: AgentRetrievalFreshness = "any"
    include_domains: list[str] = Field(default_factory=list)
    exclude_domains: list[str] = Field(default_factory=list)

    @field_validator("country")
    @classmethod
    def normalize_country(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("country must not be empty")
        return normalized

    @field_validator("language")
    @classmethod
    def normalize_language(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("language must not be empty")
        return normalized

    @field_validator("include_domains", "exclude_domains")
    @classmethod
    def normalize_domains(cls, values: list[str]) -> list[str]:
        normalized = sorted({value.strip().lower() for value in values if value.strip()})
        return normalized


class AgentRunRetrievalFetchPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_age_ms: int = Field(default=300_000, ge=0)
    fresh: bool = False


class AgentRunRetrievalPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    search: AgentRunRetrievalSearchPolicy = Field(
        default_factory=AgentRunRetrievalSearchPolicy
    )
    fetch: AgentRunRetrievalFetchPolicy = Field(
        default_factory=AgentRunRetrievalFetchPolicy
    )


class AgentSourceReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    url: HttpUrl
    snippet: str = ""

    @model_validator(mode="before")
    @classmethod
    def populate_source_id(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value

        record = dict(value)
        source_id = record.get("source_id")
        if isinstance(source_id, str) and source_id.strip():
            record["source_id"] = source_id.strip()
            return record

        url = record.get("url")
        title = record.get("title")
        record["source_id"] = _build_source_id(
            str(url).strip() if url is not None else None,
            str(title).strip() if title is not None else None,
        )
        return record

    @field_validator("source_id", "title", "snippet")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def validate_title(self) -> "AgentSourceReference":
        if not self.title:
            raise ValueError("source title must not be empty")
        return self


class AgentAnswerCitation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(min_length=1)
    start_index: int = Field(ge=0)
    end_index: int = Field(gt=0)

    @field_validator("source_id")
    @classmethod
    def normalize_source_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("citation source_id must not be empty")
        return normalized

    @model_validator(mode="after")
    def validate_span(self) -> "AgentAnswerCitation":
        if self.end_index <= self.start_index:
            raise ValueError("citation end_index must be greater than start_index")
        return self


class AgentStructuredAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    citations: list[AgentAnswerCitation] = Field(default_factory=list)

    @field_validator("text")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("answer text must not be empty")
        return normalized


class AgentRunResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)
    status: AgentRunStatus
    final_answer: Optional[AgentStructuredAnswer] = None
    sources: list[AgentSourceReference] = Field(default_factory=list)
    tool_call_count: int = Field(ge=0)
    elapsed_ms: int = Field(ge=0)
    error: Optional[AgentRunError] = None

    @model_validator(mode="before")
    @classmethod
    def coerce_legacy_final_answer(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value

        record = dict(value)
        final_answer = record.get("final_answer")
        if isinstance(final_answer, str):
            normalized = final_answer.strip()
            record["final_answer"] = None if not normalized else {"text": normalized}
        return record

    @model_validator(mode="after")
    def validate_status_fields(self) -> "AgentRunResult":
        if self.status == "completed":
            if self.final_answer is None:
                raise ValueError("completed runs require a final_answer")
            if self.error is not None:
                raise ValueError("completed runs cannot include an error")
            return self

        if self.error is None:
            raise ValueError("failed runs require an error")
        return self


@dataclass(frozen=True)
class AgentRuntimeProfile:
    name: AgentRunMode
    model: str
    recursion_limit: int
    timeout_seconds: int
    execution_mode: AgentRuntimeExecutionMode
    max_tool_steps: int
    max_search_results: int
    max_crawl_chars: int


def _build_source_id(url: str | None, title: str | None) -> str:
    candidate = url or title or "source"
    normalized = re.sub(r"[^a-z0-9]+", "-", candidate.lower()).strip("-")
    return normalized or "source"
