from __future__ import annotations

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from backend.api.contracts import AgentRunRequest, AgentRunSuccessResponse
from backend.api.errors import AgentRunErrorResponse
from backend.api.services.agent_run import execute_agent_run_request

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
async def run_agent(
    request: Request,
    response: Response,
    payload: AgentRunRequest,
) -> AgentRunSuccessResponse | JSONResponse:
    route_response = execute_agent_run_request(request, payload)
    if isinstance(route_response, JSONResponse):
        _set_route_headers(route_response)
        return route_response

    _set_route_headers(response)
    return route_response


def _set_route_headers(response: Response) -> None:
    response.headers["x-run-route"] = "legacy-compat"
    response.headers["x-run-execution-surface"] = "sync"
