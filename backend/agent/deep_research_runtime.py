from __future__ import annotations

from typing import Callable
from uuid import uuid4

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
from backend.agent.schemas.deep_research import (
    DeepResearchJob,
    DeepResearchPlan,
    DeepResearchStage,
)
from backend.api.schemas import (
    AgentRunQueuedMetadata,
    AgentRunQueuedResponse,
)


def start_deep_research(
    *,
    prompt: str,
    retrieval_policy: AgentRunRetrievalPolicy,
    store: InMemoryDeepResearchStore | None = None,
    schedule_job: Callable[[str], None] | None = None,
    run_id_factory: Callable[[], str] | None = None,
) -> AgentRunQueuedResponse:
    deep_research_store = store or get_default_deep_research_store()
    job_id = (run_id_factory or _default_run_id_factory)()
    job = DeepResearchJob(
        job_id=job_id,
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
    plan_builder: Callable[[DeepResearchJob], list[str] | DeepResearchPlan] = build_deep_research_plan,
    wave_executor: Callable[[DeepResearchJob], DeepResearchJob] = execute_research_waves,
    verifier: Callable[[DeepResearchJob], DeepResearchJob] = verify_deep_research_job,
    finalizer: Callable[[DeepResearchJob], DeepResearchJob] = finalize_deep_research_answer,
) -> DeepResearchJob:
    deep_research_store = store or get_default_deep_research_store()
    job = deep_research_store.get_required(job_id)

    try:
        plan = plan_builder(job)
        sub_questions = plan.sub_questions if isinstance(plan, DeepResearchPlan) else plan
        job = job.model_copy(
            update={
                "stage": DeepResearchStage.PLANNING,
                "sub_questions": sub_questions,
            }
        )
        deep_research_store.save(job)

        job = wave_executor(job)
        deep_research_store.save(job)

        job = verifier(job)
        deep_research_store.save(job)

        job = job.model_copy(update={"stage": DeepResearchStage.SYNTHESIZING})
        deep_research_store.save(job)

        job = finalizer(job)
        return deep_research_store.save(job)
    except Exception as exc:
        failed_job = job.model_copy(
            update={
                "stage": DeepResearchStage.FAILED,
                "error": {
                    "category": "internal_error",
                    "message": str(exc) or "deep research job failed",
                    "retryable": False,
                },
            }
        )
        return deep_research_store.save(failed_job)


def _default_run_id_factory() -> str:
    return str(uuid4())
