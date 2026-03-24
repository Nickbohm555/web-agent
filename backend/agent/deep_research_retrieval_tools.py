from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from backend.agent.schemas import AgentRunRetrievalPolicy
from backend.app.tools.schemas.web_crawl import WebCrawlInput
from backend.app.tools.web_crawl import run_web_crawl
from backend.app.tools.web_search import build_web_search_tool


def build_deep_research_retrieval_tools(
    *,
    retrieval_policy: AgentRunRetrievalPolicy,
    max_search_results: int = 8,
    max_content_chars: int = 12000,
) -> tuple[Any, Any]:
    search_tool = build_web_search_tool(
        max_results_cap=max_search_results,
        retrieval_policy=retrieval_policy,
    )

    @tool("open_url", args_schema=WebCrawlInput)
    def open_url(
        url: str | None = None,
        urls: list[str] | None = None,
        objective: str | None = None,
    ) -> Any:
        """Open one allowed page or a small batch through the existing web_crawl pipeline and return its typed crawl payload."""
        return run_web_crawl(
            url=url,
            urls=urls,
            objective=objective,
            retrieval_policy=retrieval_policy,
        )

    if hasattr(open_url, "description"):
        open_url.description = (
            "Open one allowed URL or a small batch through the existing crawl pipeline. "
            "Returns the same typed single-page or batch crawl payloads as web_crawl, "
            "with retrieval-policy filtering and bounded content."
        )

    return search_tool, open_url
