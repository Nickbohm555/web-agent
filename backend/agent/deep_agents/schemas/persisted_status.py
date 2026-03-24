from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.agent.schemas import AgentRunError
from backend.agent.schemas.deep_research import DeepResearchStage


class PersistedStatusArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)
    thread_id: str = Field(min_length=1)
    stage: DeepResearchStage
    artifact_path: str = Field(min_length=1)
    sub_questions: list[str] = Field(default_factory=list)
    error: Optional[AgentRunError] = None
