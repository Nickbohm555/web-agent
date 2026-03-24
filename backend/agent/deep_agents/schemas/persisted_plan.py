from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PersistedPlanArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    plan_markdown: str = Field(min_length=1)
    sub_questions: list[str] = Field(default_factory=list)
