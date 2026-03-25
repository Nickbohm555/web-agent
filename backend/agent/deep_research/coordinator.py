from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from backend.agent.schemas import AgentSourceReference
from backend.api.schemas.chat.message import ChatMessage
from backend.agent.deep_research.decomposition import build_research_plan
from backend.agent.deep_research.history_inspection import last_assistant_message
from backend.agent.deep_research.synthesis import synthesize_clarification_request


class DeepResearchCoordinatorAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    sources: list[AgentSourceReference] = Field(default_factory=list)


class DeepResearchCoordinator:
    def respond(
        self,
        *,
        thread_id: str,
        history: list[ChatMessage],
        latest_user_message: str,
    ) -> DeepResearchCoordinatorAnswer:
        del thread_id
        prior_assistant = last_assistant_message(history)
        if prior_assistant is None:
            return DeepResearchCoordinatorAnswer(text=synthesize_clarification_request())

        if "Need one more detail" in prior_assistant.content:
            return DeepResearchCoordinatorAnswer(
                text=build_research_plan(latest_user_message),
            )

        return DeepResearchCoordinatorAnswer(
            text=build_research_plan(latest_user_message),
        )
