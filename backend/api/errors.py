from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from backend.agent.types import AgentRunResult


class AgentRunApiError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    retryable: bool


class AgentRunErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: AgentRunApiError


@dataclass(frozen=True)
class AgentRunHttpError:
    status_code: int
    payload: AgentRunErrorResponse


_RUNTIME_ERROR_MAP = {
    "invalid_prompt": (400, "invalid_prompt"),
    "loop_limit": (422, "loop_limit_exceeded"),
    "tool_failure": (502, "tool_execution_failed"),
    "provider_failure": (503, "provider_request_failed"),
    "timeout": (504, "agent_timeout"),
    "internal_error": (500, "internal_runtime_error"),
}


def map_runtime_failure(result: AgentRunResult) -> AgentRunHttpError:
    if result.status != "failed" or result.error is None:
        raise ValueError("runtime failure mapping requires a failed agent run result")

    status_code, error_code = _RUNTIME_ERROR_MAP[result.error.category]
    return AgentRunHttpError(
        status_code=status_code,
        payload=AgentRunErrorResponse(
            error=AgentRunApiError(
                code=error_code,
                message=result.error.message,
                retryable=result.error.retryable,
            )
        ),
    )
