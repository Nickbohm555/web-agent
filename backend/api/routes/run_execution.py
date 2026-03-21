from __future__ import annotations

from collections.abc import Callable

from fastapi.responses import JSONResponse

from backend.agent.types import AgentRunMode, AgentRunResult
from backend.api.contracts import AgentRunRequest, AgentRunSuccessResponse
from backend.api.errors import map_runtime_failure

AgentRuntimeRunner = Callable[[str, AgentRunMode], AgentRunResult]


def execute_agent_run_request(
    runner: AgentRuntimeRunner,
    payload: AgentRunRequest,
) -> AgentRunSuccessResponse | JSONResponse:
    result = runner(payload.prompt, payload.mode)

    if result.status == "failed":
        mapped_error = map_runtime_failure(result)
        return JSONResponse(
            status_code=mapped_error.status_code,
            content=mapped_error.payload.model_dump(),
        )

    return AgentRunSuccessResponse.from_run_result(result)
