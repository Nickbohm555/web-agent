from __future__ import annotations

from backend.agent.runtime_constants import QUICK_RUNTIME_MAX_CRAWLS
from backend.app.tools.schemas.web_search import WebSearchResponse


def select_quick_urls(
    response: WebSearchResponse,
    *,
    max_urls: int = QUICK_RUNTIME_MAX_CRAWLS,
) -> list[str]:
    """Select the top unique allowed result URLs for quick crawling.

    Example input: `select_quick_urls(response, max_urls=3)`
    Example output: `["https://example.com/a", "https://example.com/b"]`
    """
    seen: set[str] = set()
    selected: list[str] = []

    for result in response.results:
        url = str(result.url)
        if url in seen:
            continue

        seen.add(url)
        selected.append(url)
        if len(selected) >= max_urls:
            break

    return selected
