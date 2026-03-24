from __future__ import annotations

import logging

from backend.agent.deep_agents.persistence.artifacts import DeepResearchArtifactRepository
from backend.agent.deep_agents.schemas.persisted_status import PersistedStatusArtifact
from backend.agent.schemas import AgentRunError
from backend.agent.schemas.deep_research import DeepResearchJob, DeepResearchStage

LOGGER = logging.getLogger(__name__)


def log_deep_research_stage(
    job: DeepResearchJob,
    *,
    stage: DeepResearchStage,
    artifact_repository: DeepResearchArtifactRepository,
    artifact_path: str,
    error: AgentRunError | None = None,
    emit_log=None,
) -> DeepResearchJob:
    updated_job = job.model_copy(update={"stage": stage, "error": error})
    status_artifact = PersistedStatusArtifact(
        run_id=updated_job.job_id,
        thread_id=updated_job.thread_id,
        stage=stage,
        artifact_path=artifact_path,
        sub_questions=list(updated_job.sub_questions),
        error=error,
    )
    artifact_repository.write_status(status_artifact)
    payload = {
        "run_id": updated_job.job_id,
        "thread_id": updated_job.thread_id,
        "stage": stage.value,
        "artifact_path": artifact_path,
    }
    if emit_log is not None:
        emit_log(payload)
    else:
        LOGGER.info("deep_research_stage", extra=payload)
    return updated_job
