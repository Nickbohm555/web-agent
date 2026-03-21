from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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


class AgentRunResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)
    status: AgentRunStatus
    final_answer: str = ""
    tool_call_count: int = Field(ge=0)
    elapsed_ms: int = Field(ge=0)
    error: Optional[AgentRunError] = None

    @model_validator(mode="after")
    def validate_status_fields(self) -> "AgentRunResult":
        if self.status == "completed":
            if not self.final_answer.strip():
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
