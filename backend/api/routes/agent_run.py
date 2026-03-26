from __future__ import annotations

import json
from typing import Literal, Union

from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse

from backend.api.schemas import (
    AgentRunQueuedResponse,
    AgentRunRequest,
    AgentRunSuccessResponse,
)
from backend.api.errors import AgentRunErrorResponse
from backend.api.services.agent_run import (
    execute_agent_run_request,
)

router = APIRouter()


@router.post(
    "/api/agent/run",
    response_model=Union[AgentRunSuccessResponse, AgentRunQueuedResponse],
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
    _request: Request,
    response: Response,
    payload: AgentRunRequest,
) -> Union[AgentRunSuccessResponse, AgentRunQueuedResponse, JSONResponse]:
    route_response = execute_agent_run_request(payload)
    if isinstance(route_response, JSONResponse):
        _set_route_headers(
            route_response,
            execution_surface=_infer_execution_surface(route_response),
        )
        return route_response

    _set_route_headers(response)
    return route_response

def _set_route_headers(
    response: Response,
    *,
    execution_surface: Literal["sync", "background"] = "sync",
) -> None:
    response.headers["x-run-route"] = "legacy-compat"
    response.headers["x-run-execution-surface"] = execution_surface


def _infer_execution_surface(response: JSONResponse) -> Literal["sync", "background"]:
    payload = json.loads(response.body.decode("utf-8"))
    if isinstance(payload, dict) and payload.get("status") in {"queued", "running"}:
        return "background"
    return "sync"
