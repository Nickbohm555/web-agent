from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.agent.types import AgentRunMode, AgentRunResult
from backend.api.contracts import AgentRunRequest, AgentRunSuccessResponse
from backend.api.errors import AgentRunErrorResponse, map_runtime_failure

router = APIRouter()


@router.post(
    "/api/agent/run",
    response_model=AgentRunSuccessResponse,
    responses={
        400: {"model": AgentRunErrorResponse},
        422: {"model": AgentRunErrorResponse},
        500: {"model": AgentRunErrorResponse},
        502: {"model": AgentRunErrorResponse},
        503: {"model": AgentRunErrorResponse},
        504: {"model": AgentRunErrorResponse},
    },
)
async def run_agent(request: Request, payload: AgentRunRequest) -> AgentRunSuccessResponse | JSONResponse:
    runner = _get_runtime_runner(request)
    result = runner(payload.prompt, payload.mode)

    if result.status == "failed":
        mapped_error = map_runtime_failure(result)
        return JSONResponse(
            status_code=mapped_error.status_code,
            content=mapped_error.payload.model_dump(),
        )

    return AgentRunSuccessResponse.from_run_result(result)


def _get_runtime_runner(request: Request) -> Callable[[str, AgentRunMode], AgentRunResult]:
    runner = getattr(request.app.state, "run_agent_once", None)
    if runner is None:
        raise RuntimeError("agent runtime is not configured")
    return runner
