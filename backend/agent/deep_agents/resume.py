from __future__ import annotations

import asyncio
from typing import Protocol

from backend.agent.deep_agents.persistence.artifacts import DeepResearchArtifactRepository
from backend.agent.deep_agents.persistence.checkpointer import create_deep_research_checkpointer
from backend.agent.schemas.deep_research import DeepResearchJob
from backend.app.config import Settings


class DeepResearchCheckpointRepository(Protocol):
    def has_thread(self, thread_id: str) -> bool: ...


class PostgresCheckpointRepository:
    def __init__(self, *, settings: Settings | None = None) -> None:
        self._settings = settings

    def has_thread(self, thread_id: str) -> bool:
        return asyncio.run(self._has_thread(thread_id))

    async def _has_thread(self, thread_id: str) -> bool:
        async with create_deep_research_checkpointer(settings=self._settings) as saver:
            checkpoint = await saver.aget_tuple({"configurable": {"thread_id": thread_id}})
        return checkpoint is not None


def build_deep_research_thread_id(run_id: str) -> str:
    return f"thread-{run_id}"


def restore_deep_research_job(
    job: DeepResearchJob,
    *,
    artifact_repository: DeepResearchArtifactRepository,
    checkpoint_repository: DeepResearchCheckpointRepository,
) -> DeepResearchJob:
    status = artifact_repository.read_status(job.job_id)
    if status is None or not checkpoint_repository.has_thread(job.thread_id):
        return job

    sub_questions = artifact_repository.read_subquestions(job.job_id) or status.sub_questions
    return job.model_copy(
        update={
            "thread_id": status.thread_id,
            "stage": status.stage,
            "sub_questions": sub_questions,
        }
    )
