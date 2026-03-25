from __future__ import annotations

from fastapi.responses import JSONResponse

from backend.agent.runtime import run_agent_once
from backend.api.errors import AgentRunApiError, AgentRunErrorResponse, map_runtime_failure
from backend.api.schemas import AgentRunRequest, AgentRunSuccessResponse


def execute_agent_run_request(
    payload: AgentRunRequest,
) -> AgentRunSuccessResponse | JSONResponse:
    if payload.mode != "quick":
        return JSONResponse(
            status_code=400,
            content=AgentRunErrorResponse(
                error=AgentRunApiError(
                    code="UNSUPPORTED_MODE",
                    message="Use thread-based chat routes for agentic and deep research.",
                    retryable=False,
                )
            ).model_dump(),
        )

    result = run_agent_once(payload.prompt, payload.mode)

    if result.status == "failed":
        mapped_error = map_runtime_failure(result)
        return JSONResponse(
            status_code=mapped_error.status_code,
            content=mapped_error.payload.model_dump(),
        )

    return AgentRunSuccessResponse.from_run_result(result)
