from __future__ import annotations

from backend.agent.schemas.deep_research import DeepResearchJob, DeepResearchPlan


def build_deep_research_plan(job: DeepResearchJob) -> DeepResearchPlan:
    return DeepResearchPlan(sub_questions=[job.prompt])
