from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from backend.agent.runtime_constants import (
    STANDARD_AGENT_MAX_CRAWL_CHARS,
    STANDARD_AGENT_MAX_SEARCH_RESULTS,
)
from backend.app.tools.schemas.open_url import OpenUrlInput
from backend.app.tools.open_url import run_open_url
from backend.app.tools.web_search import build_web_search_tool


def build_deep_research_retrieval_tools(
    *,
    max_search_results: int = STANDARD_AGENT_MAX_SEARCH_RESULTS,
    max_content_chars: int = STANDARD_AGENT_MAX_CRAWL_CHARS,
) -> tuple[Any, Any]:
    search_tool = build_web_search_tool(
        max_results_cap=max_search_results,
    )

    @tool("open_url", args_schema=OpenUrlInput)
    def open_url(
        url: str | None = None,
        urls: list[str] | None = None,
    ) -> Any:
        """Open one page or a small batch through the existing open_url pipeline and return its typed crawl payload."""
        return run_open_url(
            url=url,
            urls=urls,
        )

    if hasattr(open_url, "description"):
        open_url.description = (
            "Open one URL or a small batch through the existing crawl pipeline. "
            "Returns the same typed single-page or batch crawl payloads as open_url."
        )

    return search_tool, open_url
