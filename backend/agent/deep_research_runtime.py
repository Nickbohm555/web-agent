from __future__ import annotations

from uuid import uuid4

from backend.agent.deep_agents import logging as deep_research_logging
from backend.agent.deep_agents.persistence.artifacts import (
    PostgresArtifactRepository,
    final_answer_artifact_path,
    plan_artifact_path,
    status_artifact_path,
)
from backend.agent.deep_agents.resume import (
    PostgresCheckpointRepository,
    build_deep_research_thread_id,
    restore_deep_research_job,
)
from backend.agent.deep_agents.supervisor import (
    build_deep_research_supervisor,
    persist_research_plan,
)
from backend.agent.deep_research_execution import execute_research_waves
from backend.agent.deep_research_planning import build_deep_research_plan
from backend.agent.deep_research_store import (
    InMemoryDeepResearchStore,
    get_default_deep_research_store,
)
from backend.agent.deep_research_verification import (
    finalize_deep_research_answer,
    verify_deep_research_job,
)
from backend.agent.schemas import AgentRunRetrievalPolicy
from backend.agent.schemas.deep_research import DeepResearchJob, DeepResearchStage
from backend.api.schemas import AgentRunQueuedMetadata, AgentRunQueuedResponse


def start_deep_research(
    *,
    prompt: str,
    retrieval_policy: AgentRunRetrievalPolicy,
    store: InMemoryDeepResearchStore | None = None,
    schedule_job=None,
    run_id_factory=None,
    thread_id_factory=None,
) -> AgentRunQueuedResponse:
    deep_research_store = store or get_default_deep_research_store()
    job_id = (run_id_factory or _default_run_id_factory)()
    thread_id = (thread_id_factory or build_deep_research_thread_id)(job_id)
    job = DeepResearchJob(
        job_id=job_id,
        thread_id=thread_id,
        prompt=prompt,
        retrieval_policy=retrieval_policy,
        stage=DeepResearchStage.QUEUED,
    )
    deep_research_store.save(job)
    if schedule_job is not None:
        schedule_job(job.job_id)
    return AgentRunQueuedResponse(
        run_id=job.job_id,
        status="queued",
        metadata=AgentRunQueuedMetadata(execution_surface="background"),
    )


def run_deep_research_job(
    job_id: str,
    *,
    store: InMemoryDeepResearchStore | None = None,
    artifact_repository=None,
    checkpoint_repository=None,
    plan_builder=None,
    supervisor_builder=None,
    resume_state_loader=None,
    wave_executor=None,
    verifier=None,
    finalizer=None,
) -> DeepResearchJob:
    deep_research_store = store or get_default_deep_research_store()
    artifacts = artifact_repository or PostgresArtifactRepository()
    checkpoints = checkpoint_repository or PostgresCheckpointRepository()
    job = deep_research_store.get_required(job_id)

    try:
        restored_job = (resume_state_loader or restore_deep_research_job)(
            job,
            artifact_repository=artifacts,
            checkpoint_repository=checkpoints,
        )
        job = deep_research_store.save(restored_job)

        if job.stage == DeepResearchStage.QUEUED:
            job = deep_research_logging.log_deep_research_stage(
                job,
                stage=DeepResearchStage.PLANNING,
                artifact_repository=artifacts,
                artifact_path=status_artifact_path(job.job_id),
            )
            job = persist_research_plan(
                job,
                artifact_repository=artifacts,
                plan_builder=plan_builder or build_deep_research_plan,
                supervisor_builder=supervisor_builder or build_deep_research_supervisor,
            )
            job = deep_research_logging.log_deep_research_stage(
                job,
                stage=DeepResearchStage.PLANNING,
                artifact_repository=artifacts,
                artifact_path=plan_artifact_path(job.job_id),
            )
            deep_research_store.save(job)

        job = (wave_executor or execute_research_waves)(job)
        job = deep_research_logging.log_deep_research_stage(
            job,
            stage=DeepResearchStage.SEARCHING,
            artifact_repository=artifacts,
            artifact_path=status_artifact_path(job.job_id),
        )
        deep_research_store.save(job)

        job = (verifier or verify_deep_research_job)(job)
        job = deep_research_logging.log_deep_research_stage(
            job,
            stage=DeepResearchStage.VERIFYING,
            artifact_repository=artifacts,
            artifact_path=status_artifact_path(job.job_id),
        )
        deep_research_store.save(job)

        job = deep_research_logging.log_deep_research_stage(
            job,
            stage=DeepResearchStage.SYNTHESIZING,
            artifact_repository=artifacts,
            artifact_path=status_artifact_path(job.job_id),
        )
        deep_research_store.save(job)

        job = (finalizer or finalize_deep_research_answer)(job)
        if job.final_answer is not None:
            artifacts.write_final_answer(
                run_id=job.job_id,
                markdown=_final_answer_text(job.final_answer),
            )
        job = deep_research_logging.log_deep_research_stage(
            job,
            stage=DeepResearchStage.COMPLETED,
            artifact_repository=artifacts,
            artifact_path=final_answer_artifact_path(job.job_id),
        )
        return deep_research_store.save(job)
    except Exception as exc:
        failed_job = deep_research_logging.log_deep_research_stage(
            job,
            stage=DeepResearchStage.FAILED,
            artifact_repository=artifacts,
            artifact_path=status_artifact_path(job.job_id),
            error={
                "category": "internal_error",
                "message": str(exc) or "deep research job failed",
                "retryable": False,
            },
        )
        return deep_research_store.save(failed_job)


def _default_run_id_factory() -> str:
    return str(uuid4())


def _final_answer_text(final_answer: object) -> str:
    if hasattr(final_answer, "text"):
        return str(final_answer.text)
    if isinstance(final_answer, dict):
        return str(final_answer.get("text", ""))
    return str(final_answer)
