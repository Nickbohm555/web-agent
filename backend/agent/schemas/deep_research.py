from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.agent.schemas import (
    AgentRunError,
    AgentRunRetrievalPolicy,
    AgentSourceReference,
    AgentStructuredAnswer,
)


class DeepResearchStage(str, Enum):
    QUEUED = "queued"
    PLANNING = "planning"
    SEARCHING = "searching"
    VERIFYING = "verifying"
    SYNTHESIZING = "synthesizing"
    COMPLETED = "completed"
    FAILED = "failed"


class DeepResearchJob(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(min_length=1)
    thread_id: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    retrieval_policy: AgentRunRetrievalPolicy = Field(default_factory=AgentRunRetrievalPolicy)
    stage: DeepResearchStage
    sub_questions: list[str] = Field(default_factory=list)
    sources: list[AgentSourceReference] = Field(default_factory=list)
    wave_count: int = Field(default=0, ge=0)
    final_answer: Optional[AgentStructuredAnswer] = None
    error: Optional[AgentRunError] = None


class DeepResearchPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sub_questions: list[str] = Field(default_factory=list)
