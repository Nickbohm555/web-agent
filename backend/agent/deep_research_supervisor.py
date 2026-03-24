from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Callable

from backend.agent.deep_research_subagents import build_research_subagent
from backend.agent.runtime_constants import DEEP_RESEARCH_RUNTIME_MODE, RUNTIME_PROFILES
from backend.agent.schemas import AgentRunRetrievalPolicy


SUPERVISOR_PROMPT = (
    "You are the deep-research supervisor. Read the plan, keep the work decomposed "
    "into independent subquestions, and synthesize only after the evidence is ready. "
    "Delegate each independent subquestion to the research_subagent in parallel when "
    "the plan contains more than one subquestion."
)


def build_deep_research_supervisor(
    *,
    retrieval_policy: AgentRunRetrievalPolicy,
    create_agent: Callable[..., Any] | None = None,
    plan_subquestions: Sequence[str] | None = None,
) -> Any:
    deep_agent_factory = create_agent or _load_create_deep_agent()
    subagent = build_research_subagent(retrieval_policy=retrieval_policy)
    delegated_subagent_count = len(plan_subquestions or ())

    return deep_agent_factory(
        model=RUNTIME_PROFILES[DEEP_RESEARCH_RUNTIME_MODE].model,
        system_prompt=SUPERVISOR_PROMPT,
        subagents=[subagent],
        metadata={"delegated_subagent_count": delegated_subagent_count},
    )


def _load_create_deep_agent() -> Callable[..., Any]:
    import deepagents

    create_deep_agent = getattr(deepagents, "create_deep_agent", None)
    if create_deep_agent is None:
        raise RuntimeError("deepagents create_deep_agent API is required for Phase 4")
    return create_deep_agent
