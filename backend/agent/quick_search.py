from __future__ import annotations

import re
from typing import Any, Protocol

from backend.agent.schemas import AgentSourceReference
from backend.app.tools.schemas.web_search import WebSearchResponse
from backend.app.tools.web_search import run_web_search

DEFAULT_QUICK_SEARCH_MAX_RESULTS = 5


class QuickSearchRunner(Protocol):
    def __call__(
        self,
        *,
        query: str,
        max_results: int = DEFAULT_QUICK_SEARCH_MAX_RESULTS,
    ) -> dict[str, Any]:
        ...


def run_quick_search(
    *,
    query: str,
    max_results: int = DEFAULT_QUICK_SEARCH_MAX_RESULTS,
    search_runner: QuickSearchRunner | None = None,
) -> dict[str, Any]:
    runner = search_runner or run_web_search
    return runner(query=query, max_results=max_results)


def synthesize_quick_answer(
    *,
    prompt: str,
    sources: list[AgentSourceReference],
    response: WebSearchResponse,
) -> str:
    if not sources and not response.results:
        return f'No relevant web results were found for "{response.query}".'

    if sources:
        ranked_sources = _rank_sources(prompt, sources)
        direct_answer = _build_direct_answer(prompt, ranked_sources)
        if direct_answer is not None:
            source_lines = "\n".join(f"- {source.title}: {source.url}" for source in ranked_sources[:3])
            return f"{direct_answer}\n\nSources:\n{source_lines}"

        summary_lines = [
            f"- {source.title}: {_clean_snippet(source.snippet) or source.url}"
            for source in ranked_sources[:3]
        ]
        return "Quick answer based on the top sources:\n" + "\n".join(summary_lines)

    fallback_results = response.results[:3]
    summary_lines = [
        f"- {result.title}: {_clean_snippet(result.snippet) or result.url}"
        for result in fallback_results
    ]
    return "Quick answer based on the top search results:\n" + "\n".join(summary_lines)


def _build_direct_answer(
    prompt: str,
    sources: list[AgentSourceReference],
) -> str | None:
    normalized_prompt = " ".join(prompt.strip().split())
    capital_match = re.match(
        r"what is the capital of (?P<subject>.+?)(?:\?|$)",
        normalized_prompt,
        flags=re.IGNORECASE,
    )
    if capital_match:
        subject = capital_match.group("subject").strip().rstrip(".")
        entity = _extract_title_entity(sources[0].title)
        if entity is not None:
            return f"{entity} is the capital of {subject}."
    return None


def _extract_title_entity(title: str) -> str | None:
    entity = re.split(r"\s[-|:]\s", title, maxsplit=1)[0].strip()
    if not entity or "?" in entity:
        return None
    return entity


def _clean_snippet(snippet: str) -> str:
    normalized = " ".join(snippet.replace("\n", " ").split())
    normalized = re.sub(r"\|\s*Missing:.*$", "", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"Show results with:.*$", "", normalized, flags=re.IGNORECASE)
    return normalized.strip(" .")


def _rank_sources(
    prompt: str,
    sources: list[AgentSourceReference],
) -> list[AgentSourceReference]:
    prompt_tokens = {token for token in re.findall(r"[a-z0-9]+", prompt.lower()) if len(token) > 2}

    def score(source: AgentSourceReference) -> tuple[int, int, str]:
        title = source.title.lower()
        snippet = source.snippet.lower()
        penalty = 0
        if "?" in source.title:
            penalty += 3
        if any(marker in title for marker in ("riddle", "quiz", "youtube", "shorts")):
            penalty += 3
        if not source.snippet.strip():
            penalty += 2
        token_matches = sum(1 for token in prompt_tokens if token in title or token in snippet)
        return (penalty, -token_matches, source.title)

    return sorted(sources, key=score)
