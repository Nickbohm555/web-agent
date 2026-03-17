from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


AgentRunStatus = Literal["completed", "failed"]


class AgentRunResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)
    status: AgentRunStatus
    final_answer: str = Field(min_length=1)
    tool_call_count: int = Field(ge=0)
    elapsed_ms: int = Field(ge=0)
