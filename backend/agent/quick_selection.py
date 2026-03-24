from __future__ import annotations

from backend.agent.runtime_constants import QUICK_RUNTIME_MAX_CRAWLS
from backend.agent.schemas import AgentRunRetrievalPolicy
from backend.app.tools._tool_utils import domain_scope_kwargs, is_url_allowed
from backend.app.tools.schemas.web_search import WebSearchResponse


def select_quick_urls(
    response: WebSearchResponse,
    *,
    retrieval_policy: AgentRunRetrievalPolicy,
    max_urls: int = QUICK_RUNTIME_MAX_CRAWLS,
) -> list[str]:
    """Select the top unique allowed result URLs for quick crawling.

    Example input: `select_quick_urls(response, retrieval_policy=policy, max_urls=3)`
    Example output: `["https://example.com/a", "https://example.com/b"]`
    """
    seen: set[str] = set()
    selected: list[str] = []
    scope = domain_scope_kwargs(retrieval_policy.search)

    for result in response.results:
        url = str(result.url)
        if url in seen:
            continue
        if not is_url_allowed(url, **scope):
            continue

        seen.add(url)
        selected.append(url)
        if len(selected) >= max_urls:
            break

    return selected
