from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from backend.agent.schemas import AgentAnswerCitation, AgentSourceReference


class DeepResearchSubagentAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subquestion: str = Field(min_length=1)
    subquestion_index: int = Field(ge=0)


class DeepResearchArtifactRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subquestion: str = Field(min_length=1)
    artifact_path: str = Field(min_length=1)


class DeepResearchSubagentResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subquestion: str = Field(min_length=1)
    subanswer: str = Field(min_length=1)
    sources: list[AgentSourceReference] = Field(default_factory=list)
    citations: list[AgentAnswerCitation] = Field(default_factory=list)
    artifact_path: str | None = None
