from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.agent.schemas import (
    AgentStructuredAnswer,
    AgentRunMode,
    AgentRunResult,
    AgentRunRetrievalPolicy,
    AgentSourceReference,
)


class AgentRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=1)
    mode: AgentRunMode
    retrieval_policy: AgentRunRetrievalPolicy = Field(default_factory=AgentRunRetrievalPolicy)

    @model_validator(mode="before")
    @classmethod
    def map_retrieval_policy_alias(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value
        if "retrievalPolicy" in value and "retrieval_policy" not in value:
            mapped = dict(value)
            mapped["retrieval_policy"] = mapped.pop("retrievalPolicy")
            return mapped
        return value

    @field_validator("prompt")
    @classmethod
    def validate_prompt(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("prompt must not be empty")
        return normalized


class AgentRunMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_call_count: int = Field(ge=0)
    elapsed_ms: int = Field(ge=0)

    @classmethod
    def from_run_result(cls, result: AgentRunResult) -> "AgentRunMetadata":
        return cls(
            tool_call_count=result.tool_call_count,
            elapsed_ms=result.elapsed_ms,
        )


class AgentRunSuccessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)
    status: Literal["completed"]
    final_answer: AgentStructuredAnswer
    sources: list[AgentSourceReference] = Field(default_factory=list)
    tool_call_count: int = Field(ge=0)
    elapsed_ms: int = Field(ge=0)
    metadata: AgentRunMetadata

    @classmethod
    def from_run_result(cls, result: AgentRunResult) -> "AgentRunSuccessResponse":
        if result.status != "completed":
            raise ValueError("completed response requires a successful agent run result")
        return cls(
            run_id=result.run_id,
            status=result.status,
            final_answer=result.final_answer,
            sources=result.sources,
            tool_call_count=result.tool_call_count,
            elapsed_ms=result.elapsed_ms,
            metadata=AgentRunMetadata.from_run_result(result),
        )
