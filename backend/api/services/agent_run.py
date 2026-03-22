from __future__ import annotations

from collections.abc import Callable

from fastapi.responses import JSONResponse

from backend.agent.types import AgentRunMode, AgentRunResult, AgentRunRetrievalPolicy
from backend.api.contracts import AgentRunRequest, AgentRunSuccessResponse
from backend.api.errors import map_runtime_failure


def execute_agent_run_request(
    run_agent_once: Callable[
        [str, AgentRunMode, AgentRunRetrievalPolicy],
        AgentRunResult,
    ],
    payload: AgentRunRequest,
) -> AgentRunSuccessResponse | JSONResponse:
    result = run_agent_once(
        payload.prompt,
        payload.mode,
        payload.retrieval_policy,
    )

    if result.status == "failed":
        mapped_error = map_runtime_failure(result)
        return JSONResponse(
            status_code=mapped_error.status_code,
            content=mapped_error.payload.model_dump(),
        )

    return AgentRunSuccessResponse.from_run_result(result)
