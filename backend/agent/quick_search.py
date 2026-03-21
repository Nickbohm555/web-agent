from __future__ import annotations

from typing import Any, Protocol

from backend.app.contracts.web_search import WebSearchResponse
from backend.app.tools.web_search import run_web_search

DEFAULT_QUICK_SEARCH_MAX_RESULTS = 5


class QuickSearchRunner(Protocol):
    def __call__(
        self,
        *,
        query: str,
        max_results: int = DEFAULT_QUICK_SEARCH_MAX_RESULTS,
        freshness: str = "any",
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
    ) -> dict[str, Any]:
        ...


def run_quick_search(
    *,
    query: str,
    max_results: int = DEFAULT_QUICK_SEARCH_MAX_RESULTS,
    freshness: str = "any",
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
    search_runner: QuickSearchRunner | None = None,
) -> dict[str, Any]:
    runner = search_runner or run_web_search
    scoped_query = query
    include_terms = [f"site:{domain}" for domain in include_domains or []]
    exclude_terms = [f"-site:{domain}" for domain in exclude_domains or []]
    if include_terms or exclude_terms:
        scoped_query = f"{query} {' '.join([*include_terms, *exclude_terms])}".strip()
    return runner(query=scoped_query, max_results=max_results, freshness=freshness)


def synthesize_quick_answer(response: WebSearchResponse) -> str:
    if not response.results:
        return f'No relevant web results were found for "{response.query}".'

    top_results = response.results[:3]
    summaries: list[str] = []
    for result in top_results:
        snippet = result.snippet.rstrip(".")
        summaries.append(f"{result.title}: {snippet}.")

    sources = "\n".join(f"- {result.title}: {result.url}" for result in top_results)
    summary_text = " ".join(summaries)
    return f'{summary_text}\n\nSources:\n{sources}'
