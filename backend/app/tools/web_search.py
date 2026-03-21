from __future__ import annotations

import re
from time import perf_counter
from typing import Any, Callable

from langchain_core.tools import tool
from pydantic import ValidationError

from backend.agent.types import (
    AgentRunRetrievalPolicy,
    AgentRunRetrievalSearchPolicy,
)
from backend.app.config import get_settings
from backend.app.contracts.web_search import SearchRank, WebSearchInput, WebSearchResponse, WebSearchResult
from backend.app.providers.serper_client import SerperClient, SerperClientError
from backend.app.tools._tool_utils import (
    build_tool_action_error_record,
    build_tool_error_payload,
    domain_scope_kwargs,
    has_domain_scope,
    is_url_allowed,
    validation_error_message,
)


def create_serper_client() -> SerperClient:
    return SerperClient(api_key=get_settings().SERPER_API_KEY)


def build_web_search_tool(
    *,
    max_results_cap: int = 5,
    retrieval_policy: AgentRunRetrievalPolicy | None = None,
    search_runner: Callable[..., dict[str, Any]] | None = None,
):
    bounded_cap = max(1, min(max_results_cap, 10))
    runner = search_runner or run_web_search

    @tool("web_search", args_schema=WebSearchInput)
    def bounded_web_search(query: str, max_results: int = 5) -> dict[str, Any]:
        """Search the web and return normalized results or a structured error envelope."""
        effective_policy = retrieval_policy or AgentRunRetrievalPolicy()
        search_policy = effective_policy.search
        domain_scope = domain_scope_kwargs(search_policy)
        payload = runner(
            query=_apply_domain_scope_to_query(query, search_policy),
            max_results=min(max_results, bounded_cap),
            freshness=search_policy.freshness,
        )
        return _filter_search_payload_by_domain_scope(payload, domain_scope)

    return bounded_web_search


def run_web_search(
    *,
    query: str,
    max_results: int = 5,
    freshness: str = "any",
    client: SerperClient | None = None,
) -> dict[str, Any]:
    operation_start = perf_counter()
    try:
        validated_input = WebSearchInput(query=query, max_results=max_results)
        response = (client or create_serper_client()).search(
            query=validated_input.query,
            max_results=validated_input.max_results,
            freshness=freshness,
        )
        validated_response = WebSearchResponse.model_validate(response)
        optimized_response = _optimize_search_response(
            query=validated_input.query,
            response=validated_response,
        )
        return optimized_response.model_dump(mode="json")
    except ValidationError as exc:
        return _build_search_error_payload(
            operation_start=operation_start,
            kind="invalid_request",
            message=validation_error_message(exc),
            retryable=False,
        )
    except SerperClientError as exc:
        return _build_search_error_payload(
            operation_start=operation_start,
            kind=exc.kind,
            message=exc.message,
            retryable=exc.retryable,
            operation=exc.operation,
            status_code=exc.status_code,
            attempt_number=exc.attempt_number or 1,
            provider_ms=exc.provider_ms,
        )
    except Exception:
        return _build_search_error_payload(
            operation_start=operation_start,
            kind="internal_error",
            message="unexpected web_search failure",
            retryable=False,
        )


web_search = build_web_search_tool()


def _elapsed_ms(start: float) -> int:
    return int((perf_counter() - start) * 1000)


def _build_search_error_payload(
    *,
    operation_start: float,
    kind: str,
    message: str,
    retryable: bool,
    operation: str = "web_search",
    status_code: int | None = None,
    attempt_number: int = 1,
    provider_ms: int | None = None,
) -> dict[str, Any]:
    return build_tool_error_payload(
        kind=kind,
        message=message,
        retryable=retryable,
        total_ms=_elapsed_ms(operation_start),
        operation=operation,
        status_code=status_code,
        attempt_number=attempt_number,
        provider_ms=provider_ms,
    )


def _apply_domain_scope_to_query(
    query: str,
    search_policy: AgentRunRetrievalSearchPolicy,
) -> str:
    include_terms = [f"site:{domain}" for domain in search_policy.include_domains]
    exclude_terms = [f"-site:{domain}" for domain in search_policy.exclude_domains]
    scope_terms = [*include_terms, *exclude_terms]

    if not scope_terms:
        return query

    return f"{query} {' '.join(scope_terms)}".strip()


def _filter_search_payload_by_domain_scope(
    payload: dict[str, Any],
    domain_scope: dict[str, list[str]],
) -> dict[str, Any]:
    if not has_domain_scope(**domain_scope):
        return payload

    try:
        response = WebSearchResponse.model_validate(payload)
    except ValidationError:
        return payload

    filtered_results = [
        result
        for result in response.results
        if is_url_allowed(str(result.url), **domain_scope)
    ]

    return response.model_copy(
        update={
            "results": filtered_results,
            "metadata": response.metadata.model_copy(
                update={"result_count": len(filtered_results)}
            ),
        }
    ).model_dump(mode="json")


def build_web_search_action_record(
    *,
    query: str,
    payload: dict[str, Any],
    preview_limit: int = 3,
) -> dict[str, Any]:
    normalized_query = query.strip()

    try:
        response = WebSearchResponse.model_validate(payload)
        preview_items = [
            {
                "title": result.title,
                "url": str(result.url),
                "snippet": result.snippet,
                "position": result.rank.position,
            }
            for result in response.results[: max(preview_limit, 0)]
        ]
        return {
            "action_type": "search",
            "query": response.query or normalized_query,
            "result_count": response.metadata.result_count,
            "provider": response.metadata.provider,
            "results_preview": preview_items,
        }
    except ValidationError:
        pass

    action_record = build_tool_action_error_record(
        action_type="search",
        subject_key="query",
        subject_value=normalized_query,
        payload=payload,
    )
    if action_record is not None:
        return action_record

    return {
        "action_type": "search",
        "query": normalized_query,
    }


_STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
}
_TOKEN_PATTERN = re.compile(r"[a-z0-9]{2,}")
_SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+|\s+\|\s+")
_MAX_SNIPPET_LENGTH = 280


def _optimize_search_response(*, query: str, response: WebSearchResponse) -> WebSearchResponse:
    ranked: list[tuple[float, int, WebSearchResult]] = []

    for fallback_position, result in enumerate(response.results, start=1):
        score = _score_result(query=query, result=result, fallback_position=fallback_position)
        ranked.append((score, fallback_position, _rewrite_result_snippet(query=query, result=result, score=score)))

    ranked.sort(
        key=lambda item: (
            -item[0],
            item[2].rank.provider_position or item[1],
            item[1],
        )
    )

    reranked_results: list[WebSearchResult] = []
    for position, (_, _, result) in enumerate(ranked, start=1):
        reranked_results.append(
            result.model_copy(
                update={
                    "rank": result.rank.model_copy(
                        update={
                            "position": position,
                        }
                    )
                }
            )
        )

    return response.model_copy(
        update={
            "results": reranked_results,
            "metadata": response.metadata.model_copy(
                update={"result_count": len(reranked_results)}
            ),
        }
    )


def _rewrite_result_snippet(*, query: str, result: WebSearchResult, score: float) -> WebSearchResult:
    optimized_snippet = _select_snippet_excerpt(query=query, result=result)
    return result.model_copy(
        update={
            "snippet": optimized_snippet,
            "rank": result.rank.model_copy(update={"rerank_score": round(score, 3)}),
        }
    )


def _score_result(*, query: str, result: WebSearchResult, fallback_position: int) -> float:
    normalized_query = query.strip().casefold()
    title = result.title.casefold()
    snippet = result.snippet.casefold()
    url = str(result.url).casefold()
    query_terms = _query_terms(query)

    score = 0.0
    if normalized_query and normalized_query in title:
        score += 8.0
    if normalized_query and normalized_query in snippet:
        score += 5.0
    if normalized_query and normalized_query in url:
        score += 2.5

    title_matches = sum(1 for term in query_terms if term in title)
    snippet_matches = sum(1 for term in query_terms if term in snippet)
    url_matches = sum(1 for term in query_terms if term in url)

    score += title_matches * 2.5
    score += snippet_matches * 1.5
    score += url_matches * 0.75

    if query_terms:
        if title_matches == len(query_terms):
            score += 3.0
        if snippet_matches == len(query_terms):
            score += 2.0
        coverage = (title_matches + snippet_matches) / (len(query_terms) * 2)
        score += coverage * 2.0

    provider_position = result.rank.provider_position or fallback_position
    score += 1 / provider_position
    return score


def _select_snippet_excerpt(*, query: str, result: WebSearchResult) -> str:
    snippet = result.snippet.strip()
    if not snippet:
        return snippet

    sentences = [segment.strip(" ;") for segment in _SENTENCE_SPLIT_PATTERN.split(snippet) if segment.strip(" ;")]
    if len(sentences) <= 1:
        return _truncate_text(snippet)

    query_terms = _query_terms(query)
    if not query_terms:
        return _truncate_text(sentences[0])

    scored_sentences = sorted(
        ((_score_excerpt_segment(segment, query_terms), index, segment) for index, segment in enumerate(sentences)),
        key=lambda item: (-item[0], item[1]),
    )

    if scored_sentences[0][0] <= 0:
        return _truncate_text(sentences[0])

    top_score, top_index, top_segment = scored_sentences[0]
    excerpt_parts = [top_segment]
    total_length = len(top_segment)

    if top_index + 1 < len(sentences):
        follow_up = sentences[top_index + 1]
        candidate_length = len(follow_up) + 2
        if total_length + candidate_length <= _MAX_SNIPPET_LENGTH:
            excerpt_parts.append(follow_up)
            total_length += candidate_length

    for segment_score, _, segment in scored_sentences[1:]:
        if segment_score <= 0 or len(excerpt_parts) >= 2:
            break
        candidate_length = len(segment) + 2
        if total_length + candidate_length > _MAX_SNIPPET_LENGTH:
            continue
        excerpt_parts.append(segment)
        total_length += candidate_length

    if top_score <= 0:
        return _truncate_text(sentences[0])
    return _truncate_text(_join_excerpt_parts(excerpt_parts))


def _score_excerpt_segment(segment: str, query_terms: set[str]) -> float:
    normalized = segment.casefold()
    score = 0.0
    for term in query_terms:
        if term in normalized:
            score += 2.0
    return score


def _query_terms(query: str) -> set[str]:
    return {
        token
        for token in _TOKEN_PATTERN.findall(query.casefold())
        if token not in _STOP_WORDS
    }


def _truncate_text(value: str, limit: int = _MAX_SNIPPET_LENGTH) -> str:
    normalized = " ".join(value.split()).strip()
    if len(normalized) <= limit:
        return normalized
    truncated = normalized[: limit - 1].rstrip()
    return f"{truncated}…"


def _join_excerpt_parts(parts: list[str]) -> str:
    if not parts:
        return ""

    joined = parts[0].strip()
    for part in parts[1:]:
        separator = "" if joined.endswith((".", "!", "?")) else "."
        joined = f"{joined}{separator} {part.strip()}"
    return joined
