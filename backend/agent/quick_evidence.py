from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from backend.agent.runtime_sources import RuntimeSourceRegistry
from backend.agent.schemas import AgentSourceReference
from backend.app.tools.schemas.open_url import OpenUrlSuccess
from backend.app.tools.schemas.web_search import WebSearchResponse


@dataclass(frozen=True)
class QuickEvidence:
    prompt: str
    search_response: WebSearchResponse
    successful_crawls: tuple[OpenUrlSuccess, ...]
    selected_urls: tuple[str, ...]
    sources: tuple[AgentSourceReference, ...]


def build_quick_evidence(
    *,
    prompt: str,
    search_response: WebSearchResponse,
    crawl_payloads: Sequence[Any],
) -> QuickEvidence:
    """Assemble the evidence bundle for a quick retrieval run.

    Example input: `build_quick_evidence(prompt="pricing", search_response=response, crawl_payloads=[payload])`
    Example output: `QuickEvidence(selected_urls=("https://example.com/a",), ...)`
    """
    registry = RuntimeSourceRegistry.empty()
    search_title_by_url = {str(result.url): result.title for result in search_response.results}

    successful_crawls: list[OpenUrlSuccess] = []
    for payload in crawl_payloads:
        try:
            success = OpenUrlSuccess.model_validate(payload)
        except Exception:
            continue

        successful_crawls.append(success)
        source_record = success.to_source_record()
        registry.register(
            url=source_record["url"],
            title=search_title_by_url.get(str(success.url), source_record["title"]),
            snippet=source_record["snippet"],
            alias_urls=success.source_alias_urls(),
        )

    sources = tuple(registry.sources())
    selected_urls = tuple(str(crawl.url) for crawl in successful_crawls)
    return QuickEvidence(
        prompt=prompt,
        search_response=search_response,
        successful_crawls=tuple(successful_crawls),
        selected_urls=selected_urls,
        sources=sources,
    )
