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
from backend.app.contracts.web_search import (
    SearchRank,
    WebSearchError,
    WebSearchInput,
    WebSearchResponse,
    WebSearchResult,
    WebSearchToolResult,
)
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
    """Build the default Serper client from environment settings.

    Example input: `create_serper_client()`
    Example output: `SerperClient(api_key="***")`
    """
    return SerperClient(api_key=get_settings().SERPER_API_KEY)


def build_web_search_tool(
    *,
    max_results_cap: int = 5,
    retrieval_policy: AgentRunRetrievalPolicy | None = None,
    search_runner: Callable[..., WebSearchToolResult] | None = None,
):
    """Build the bounded LangChain web-search tool.

    Example input: `build_web_search_tool(max_results_cap=3)`
    Example output: `StructuredTool(name="web_search", ...)`
    """
    bounded_cap = max(1, min(max_results_cap, 10))
    runner = search_runner or run_web_search

    @tool("web_search", args_schema=WebSearchInput)
    def bounded_web_search(query: str, max_results: int = 5) -> WebSearchToolResult:
        """Search the web and return typed results.

        Example input: `{"query": "agent systems", "max_results": 3}`
        Example output: `WebSearchResponse(query="agent systems", results=[...], ...)`
        """
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
) -> WebSearchToolResult:
    """Run the search pipeline without LangChain wrapping.

    Example input: `run_web_search(query="agent systems", max_results=3)`
    Example output: `WebSearchResponse(query="agent systems", results=[...], ...)`
    """
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
        return optimized_response
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
    """Convert a perf counter start value into elapsed milliseconds.

    Example input: `_elapsed_ms(123.0)`
    Example output: `17`
    """
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
) -> WebSearchError:
    """Build a typed search error envelope.

    Example input: `_build_search_error_payload(operation_start=t0, kind="invalid_request", message="query must not be blank", retryable=False)`
    Example output: `WebSearchError(error=ToolError(kind="invalid_request", ...), ...)`
    """
    envelope = build_tool_error_payload(
        kind=kind,
        message=message,
        retryable=retryable,
        total_ms=_elapsed_ms(operation_start),
        operation=operation,
        status_code=status_code,
        attempt_number=attempt_number,
        provider_ms=provider_ms,
    )
    return WebSearchError(error=envelope.error, meta=envelope.meta)


def _apply_domain_scope_to_query(
    query: str,
    search_policy: AgentRunRetrievalSearchPolicy,
) -> str:
    """Apply include/exclude domain scope terms to a search query.

    Example input: `_apply_domain_scope_to_query("agents", policy)`
    Example output: `"agents site:example.com -site:blocked.com"`
    """
    include_terms = [f"site:{domain}" for domain in search_policy.include_domains]
    exclude_terms = [f"-site:{domain}" for domain in search_policy.exclude_domains]
    scope_terms = [*include_terms, *exclude_terms]

    if not scope_terms:
        return query

    return f"{query} {' '.join(scope_terms)}".strip()


def _filter_search_payload_by_domain_scope(
    payload: WebSearchToolResult,
    domain_scope: dict[str, list[str]],
) -> WebSearchToolResult:
    """Filter search results by configured domain scope.

    Example input: `_filter_search_payload_by_domain_scope(WebSearchResponse(...), {"include_domains": ["example.com"], "exclude_domains": ["blocked.com"]})`
    Example output: `WebSearchResponse(results=[...filtered...], ...)`
    """
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

    return _with_updated_results(response, filtered_results)


def build_web_search_action_record(
    *,
    query: str,
    payload: Any,
    preview_limit: int = 3,
) -> dict[str, Any]:
    """Summarize search output for runtime action traces.

    Example input: `build_web_search_action_record(query="agents", payload=WebSearchResponse(...))`
    Example output: `{"action_type": "search", "query": "agents", "result_count": 3, ...}`
    """
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
    """Rerank and rewrite search results for the agent runtime.

    Example input: `_optimize_search_response(query="agent systems", response=WebSearchResponse(...))`
    Example output: `WebSearchResponse(results=[...reranked...], ...)`
    """
    ranked = [
        (
            score := _score_result(
                query=query,
                result=result,
                fallback_position=fallback_position,
            ),
            fallback_position,
            _rewrite_result_snippet(query=query, result=result, score=score),
        )
        for fallback_position, result in enumerate(response.results, start=1)
    ]

    ranked.sort(
        key=lambda item: (
            -item[0],
            item[2].rank.provider_position or item[1],
            item[1],
        )
    )

    reranked_results = [
        result.model_copy(
            update={
                "rank": result.rank.model_copy(update={"position": position}),
            }
        )
        for position, (_, _, result) in enumerate(ranked, start=1)
    ]

    return _with_updated_results(response, reranked_results)


def _with_updated_results(
    response: WebSearchResponse,
    results: list[WebSearchResult],
) -> WebSearchResponse:
    """Return a copy of the response with updated results and count.

    Example input: `_with_updated_results(response, [result])`
    Example output: `WebSearchResponse(metadata=SearchMetadata(result_count=1, ...), ...)`
    """
    return response.model_copy(
        update={
            "results": results,
            "metadata": response.metadata.model_copy(
                update={"result_count": len(results)}
            ),
        }
    )


def _rewrite_result_snippet(*, query: str, result: WebSearchResult, score: float) -> WebSearchResult:
    """Rewrite a result snippet and persist its rerank score.

    Example input: `_rewrite_result_snippet(query="agent systems", result=result, score=9.5)`
    Example output: `WebSearchResult(snippet="Focused excerpt", rank=SearchRank(rerank_score=9.5, ...))`
    """
    optimized_snippet = _select_snippet_excerpt(query=query, result=result)
    return result.model_copy(
        update={
            "snippet": optimized_snippet,
            "rank": result.rank.model_copy(update={"rerank_score": round(score, 3)}),
        }
    )


def _score_result(*, query: str, result: WebSearchResult, fallback_position: int) -> float:
    """Compute a reranking score for a search result.

    Example input: `_score_result(query="agent systems", result=result, fallback_position=2)`
    Example output: `11.25`
    """
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
    """Pick the most query-relevant excerpt from a result snippet.

    Example input: `_select_snippet_excerpt(query="pricing", result=result)`
    Example output: `"Pricing details for teams and enterprise plans."`
    """
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

    _, top_index, top_segment = scored_sentences[0]
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

    return _truncate_text(_join_excerpt_parts(excerpt_parts))


def _score_excerpt_segment(segment: str, query_terms: set[str]) -> float:
    """Score one snippet segment against normalized query terms.

    Example input: `_score_excerpt_segment("Pricing for teams", {"pricing", "teams"})`
    Example output: `4.0`
    """
    normalized = segment.casefold()
    score = 0.0
    for term in query_terms:
        if term in normalized:
            score += 2.0
    return score


def _query_terms(query: str) -> set[str]:
    """Extract normalized search terms minus common stop words.

    Example input: `_query_terms("What is agent systems pricing?")`
    Example output: `{"agent", "systems", "pricing"}`
    """
    return {
        token
        for token in _TOKEN_PATTERN.findall(query.casefold())
        if token not in _STOP_WORDS
    }


def _truncate_text(value: str, limit: int = _MAX_SNIPPET_LENGTH) -> str:
    """Trim text to the snippet length budget.

    Example input: `_truncate_text("A long sentence", limit=5)`
    Example output: `"A lo..."`
    """
    normalized = " ".join(value.split()).strip()
    if len(normalized) <= limit:
        return normalized
    truncated = normalized[: limit - 1].rstrip()
    return f"{truncated}…"


def _join_excerpt_parts(parts: list[str]) -> str:
    """Join excerpt segments into one readable sentence block.

    Example input: `_join_excerpt_parts(["First sentence", "Follow up"])`
    Example output: `"First sentence. Follow up"`
    """
    if not parts:
        return ""

    joined = parts[0].strip()
    for part in parts[1:]:
        separator = "" if joined.endswith((".", "!", "?")) else "."
        joined = f"{joined}{separator} {part.strip()}"
    return joined
