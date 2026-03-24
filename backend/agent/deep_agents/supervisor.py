from __future__ import annotations

from backend.agent.deep_agents.persistence.artifacts import DeepResearchArtifactRepository
from backend.agent.deep_agents.schemas.persisted_plan import PersistedPlanArtifact
from backend.agent.deep_research_planning import build_deep_research_plan
from backend.agent.schemas.deep_research import DeepResearchJob, DeepResearchPlan, DeepResearchStage


def build_deep_research_supervisor() -> object:
    from deepagents import create_deep_agent
    from backend.agent.deep_agents.persistence.backend_factory import build_deep_research_backend

    return create_deep_agent(
        model="gpt-4.1-mini",
        tools=(),
        backend=build_deep_research_backend,
        name="deep_research_supervisor",
    )


def persist_research_plan(
    job: DeepResearchJob,
    *,
    artifact_repository: DeepResearchArtifactRepository,
    plan_builder=None,
    supervisor_builder=None,
) -> DeepResearchJob:
    if supervisor_builder is None:
        build_deep_research_supervisor()
    else:
        supervisor_builder()

    plan = (plan_builder or build_deep_research_plan)(job)
    sub_questions = plan.sub_questions if isinstance(plan, DeepResearchPlan) else list(plan)
    artifact_repository.write_plan(
        PersistedPlanArtifact(
            run_id=job.job_id,
            prompt=job.prompt,
            plan_markdown=_render_plan_markdown(sub_questions),
            sub_questions=sub_questions,
        )
    )
    artifact_repository.write_subquestions(run_id=job.job_id, sub_questions=sub_questions)
    return job.model_copy(
        update={
            "stage": DeepResearchStage.PLANNING,
            "sub_questions": sub_questions,
        }
    )


def _render_plan_markdown(sub_questions: list[str]) -> str:
    return "\n".join(f"- {question}" for question in sub_questions)
