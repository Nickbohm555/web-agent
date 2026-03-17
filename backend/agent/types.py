from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


AgentRunStatus = Literal["completed", "failed"]
AgentRunErrorCategory = Literal[
    "invalid_prompt",
    "loop_limit",
    "tool_failure",
    "provider_failure",
    "timeout",
    "internal_error",
]


class AgentRunError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: AgentRunErrorCategory
    message: str = Field(min_length=1)
    retryable: bool


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
