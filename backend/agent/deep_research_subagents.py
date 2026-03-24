from __future__ import annotations

from typing import Any

from backend.agent.deep_research_retrieval_tools import build_deep_research_retrieval_tools
from backend.agent.schemas import AgentRunRetrievalPolicy


def build_research_subagent(
    *,
    retrieval_policy: AgentRunRetrievalPolicy,
    max_search_results: int = 8,
    max_content_chars: int = 12000,
) -> dict[str, Any]:
    return {
        "name": "research_subagent",
        "description": (
            "Research one assigned subquestion and return a concise subanswer "
            "with normalized evidence."
        ),
        "system_prompt": (
            "You are a deep-research worker. Answer exactly one assigned subquestion. "
            "Use web_search first, use open_url for selected pages, and return a "
            "concise subanswer plus reusable evidence."
        ),
        "tools": list(
            build_deep_research_retrieval_tools(
                retrieval_policy=retrieval_policy,
                max_search_results=max_search_results,
                max_content_chars=max_content_chars,
            )
        ),
    }
