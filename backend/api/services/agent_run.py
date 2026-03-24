from __future__ import annotations

from fastapi.responses import JSONResponse

from backend.agent.deep_agents.resume import build_deep_research_thread_id
from backend.agent.deep_research_runtime import start_deep_research
from backend.agent.runtime import run_agent_once
from backend.api.schemas import AgentRunRequest, AgentRunSuccessResponse
from backend.api.errors import map_runtime_failure


def execute_agent_run_request(
    payload: AgentRunRequest,
) -> AgentRunSuccessResponse | JSONResponse:
    if payload.mode == "deep_research":
        queued = start_deep_research_request(payload)
        return JSONResponse(status_code=202, content=queued.model_dump())

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


def start_deep_research_request(payload: AgentRunRequest):
    return start_deep_research(
        prompt=payload.prompt,
        retrieval_policy=payload.retrieval_policy,
        thread_id_factory=build_deep_research_thread_id,
    )
