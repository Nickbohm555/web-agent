from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.agent.schemas import AgentRunError, AgentSourceReference, AgentStructuredAnswer
from backend.agent.schemas.deep_research import DeepResearchJob, DeepResearchStage


class DeepResearchStatusMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    execution_surface: Literal["background"]
    stage: DeepResearchStage
    wave_count: int = Field(ge=0)


class DeepResearchStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)
    thread_id: str = Field(min_length=1)
    status: DeepResearchStage
    final_answer: AgentStructuredAnswer | None = None
    sources: list[AgentSourceReference] = Field(default_factory=list)
    error: AgentRunError | None = None
    sub_questions: list[str] = Field(default_factory=list)
    metadata: DeepResearchStatusMetadata

    @classmethod
    def from_job(cls, job: DeepResearchJob) -> "DeepResearchStatusResponse":
        return cls(
            run_id=job.job_id,
            thread_id=job.thread_id,
            status=job.stage,
            final_answer=job.final_answer,
            sources=job.sources,
            error=job.error,
            sub_questions=job.sub_questions,
            metadata=DeepResearchStatusMetadata(
                execution_surface="background",
                stage=job.stage,
                wave_count=job.wave_count,
            ),
        )
