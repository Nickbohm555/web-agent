from __future__ import annotations

from collections.abc import Callable

from fastapi.responses import JSONResponse

from backend.agent.types import AgentRunMode, AgentRunResult, AgentRunRetrievalPolicy
from backend.api.contracts import AgentRunRequest, AgentRunSuccessResponse
from backend.api.errors import map_runtime_failure

AgentRuntimeRunner = Callable[[str, AgentRunMode, AgentRunRetrievalPolicy], AgentRunResult]


def execute_agent_run_request(
    run_agent_once: AgentRuntimeRunner,
    payload: AgentRunRequest,
) -> AgentRunSuccessResponse | JSONResponse:
    result = _run_agent_once_from_request(
        run_agent_once=run_agent_once,
        payload=payload,
    )

    if result.status == "failed":
        mapped_error = map_runtime_failure(result)
        return JSONResponse(
            status_code=mapped_error.status_code,
            content=mapped_error.payload.model_dump(),
        )

    return AgentRunSuccessResponse.from_run_result(result)


def _run_agent_once_from_request(
    *,
    run_agent_once: AgentRuntimeRunner,
    payload: AgentRunRequest,
) -> AgentRunResult:
    return run_agent_once(
        payload.prompt,
        payload.mode,
        payload.retrieval_policy,
    )
