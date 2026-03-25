from __future__ import annotations

from fastapi.responses import JSONResponse

from backend.agent.deep_agents.resume import build_deep_research_thread_id
from backend.agent.deep_research_runtime import start_deep_research
from backend.agent.deep_research_store import get_default_deep_research_store
from backend.agent.runtime import run_agent_once
from backend.api.schemas import (
    AgentRunRequest,
    AgentRunSuccessResponse,
    DeepResearchStatusResponse,
)
from backend.api.errors import map_runtime_failure
from backend.api.services.deep_research_jobs import schedule_deep_research_job


def execute_agent_run_request(
    payload: AgentRunRequest,
) -> AgentRunSuccessResponse | JSONResponse:
    if payload.mode == "deep_research":
        queued = start_deep_research(
            prompt=payload.prompt,
            schedule_job=schedule_deep_research_job,
            thread_id=payload.thread_id,
            thread_id_factory=build_deep_research_thread_id,
        )
        return JSONResponse(status_code=202, content=queued.model_dump())

    result = run_agent_once(payload.prompt, payload.mode, thread_id=payload.thread_id)

    if result.status == "failed":
        mapped_error = map_runtime_failure(result)
        return JSONResponse(
            status_code=mapped_error.status_code,
            content=mapped_error.payload.model_dump(),
        )

    return AgentRunSuccessResponse.from_run_result(result)
def get_deep_research_status(run_id: str) -> DeepResearchStatusResponse | JSONResponse:
    job = get_default_deep_research_store().get(run_id)
    if job is None:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "run_not_found",
                    "message": f"Unknown deep research run: {run_id}",
                    "retryable": False,
                }
            },
        )

    return DeepResearchStatusResponse.from_job(job)
