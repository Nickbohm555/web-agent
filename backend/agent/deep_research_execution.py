from __future__ import annotations

from backend.agent.schemas.deep_research import DeepResearchJob, DeepResearchStage


def execute_research_waves(job: DeepResearchJob) -> DeepResearchJob:
    return job.model_copy(
        update={
            "stage": DeepResearchStage.SEARCHING,
            "wave_count": max(job.wave_count, 1),
        }
    )
