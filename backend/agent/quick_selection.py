from __future__ import annotations

import re
from urllib.parse import urlsplit

from backend.agent.runtime_constants import QUICK_RUNTIME_MAX_CRAWLS
from backend.app.tools.schemas.web_search import WebSearchResponse


def select_quick_urls(
    response: WebSearchResponse,
    *,
    prompt: str | None = None,
    max_urls: int = QUICK_RUNTIME_MAX_CRAWLS,
) -> list[str]:
    """Select the top unique allowed result URLs for quick crawling.

    Example input: `select_quick_urls(response, max_urls=3)`
    Example output: `["https://example.com/a", "https://example.com/b"]`
    """
    seen: set[str] = set()
    selected: list[str] = []

    ranked_results = sorted(
        response.results,
        key=lambda result: _result_score(result, prompt),
    )

    for result in ranked_results:
        url = str(result.url)
        if url in seen:
            continue

        seen.add(url)
        selected.append(url)
        if len(selected) >= max_urls:
            break

    return selected


def _result_score(result, prompt: str | None) -> tuple[int, int, str]:
    title = result.title.lower()
    host = urlsplit(str(result.url)).netloc.lower()
    penalty = 0
    if "?" in result.title:
        penalty += 3
    if any(marker in title or marker in host for marker in ("riddle", "quiz", "youtube", "shorts")):
        penalty += 3

    token_boost = 0
    if prompt:
        prompt_tokens = {
            token
            for token in re.findall(r"[a-z0-9]+", prompt.lower())
            if len(token) > 2 and token not in {"what", "with", "from", "that", "this", "answer", "briefly", "official", "sources"}
        }
        token_boost = sum(1 for token in prompt_tokens if token in title or token in host)
        if "official" in prompt.lower() and any(token in host for token in prompt_tokens):
            token_boost += 2

    provider_position = getattr(result.rank, "provider_position", None) or getattr(result.rank, "position", 0)
    return (penalty, -token_boost, provider_position)
