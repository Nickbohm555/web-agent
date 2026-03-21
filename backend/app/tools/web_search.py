from __future__ import annotations

from time import perf_counter
from typing import Any, Callable
from urllib.parse import urlparse

from langchain_core.tools import tool
from pydantic import ValidationError

from backend.agent.types import AgentRunRetrievalPolicy
from backend.app.config import get_settings
from backend.app.contracts.web_search import WebSearchInput, WebSearchResponse
from backend.app.providers.serper_client import SerperClient, SerperClientError
from backend.app.tools._tool_utils import build_tool_error_payload, validation_error_message


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
        payload = runner(
            query=_apply_domain_scope_to_query(query, effective_policy),
            max_results=min(max_results, bounded_cap),
            freshness=effective_policy.search.freshness,
        )
        return _filter_search_payload_by_domain_scope(payload, effective_policy)

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
        return validated_response.model_dump(mode="json")
    except ValidationError as exc:
        total_ms = _elapsed_ms(operation_start)
        return build_tool_error_payload(
            kind="invalid_request",
            message=validation_error_message(exc),
            retryable=False,
            total_ms=total_ms,
            operation="web_search",
        )
    except SerperClientError as exc:
        total_ms = _elapsed_ms(operation_start)
        attempts = exc.attempt_number or 1
        return build_tool_error_payload(
            kind=exc.kind,
            message=exc.message,
            retryable=exc.retryable,
            total_ms=total_ms,
            operation=exc.operation,
            status_code=exc.status_code,
            attempt_number=attempts,
            provider_ms=exc.provider_ms,
        )
    except Exception:
        total_ms = _elapsed_ms(operation_start)
        return build_tool_error_payload(
            kind="internal_error",
            message="unexpected web_search failure",
            retryable=False,
            total_ms=total_ms,
            operation="web_search",
        )


web_search = build_web_search_tool()


def _elapsed_ms(start: float) -> int:
    return int((perf_counter() - start) * 1000)


def _apply_domain_scope_to_query(
    query: str,
    retrieval_policy: AgentRunRetrievalPolicy,
) -> str:
    include_terms = [
        f"site:{domain}" for domain in retrieval_policy.search.include_domains
    ]
    exclude_terms = [
        f"-site:{domain}" for domain in retrieval_policy.search.exclude_domains
    ]
    scope_terms = [*include_terms, *exclude_terms]

    if not scope_terms:
        return query

    return f"{query} {' '.join(scope_terms)}".strip()


def _filter_search_payload_by_domain_scope(
    payload: dict[str, Any],
    retrieval_policy: AgentRunRetrievalPolicy,
) -> dict[str, Any]:
    if not retrieval_policy.search.include_domains and not retrieval_policy.search.exclude_domains:
        return payload

    try:
        response = WebSearchResponse.model_validate(payload)
    except ValidationError:
        return payload

    filtered_results = [
        result
        for result in response.results
        if _is_url_allowed(str(result.url), retrieval_policy)
    ]

    return response.model_copy(
        update={
            "results": filtered_results,
            "metadata": response.metadata.model_copy(
                update={"result_count": len(filtered_results)}
            ),
        }
    ).model_dump(mode="json")


def _is_url_allowed(url: str, retrieval_policy: AgentRunRetrievalPolicy) -> bool:
    hostname = _normalize_hostname(url)
    if hostname is None:
        return False

    if any(_hostname_matches(hostname, blocked) for blocked in retrieval_policy.search.exclude_domains):
        return False

    include_domains = retrieval_policy.search.include_domains
    if not include_domains:
        return True

    return any(_hostname_matches(hostname, allowed) for allowed in include_domains)


def _hostname_matches(hostname: str, domain: str) -> bool:
    return hostname == domain or hostname.endswith(f".{domain}")


def _normalize_hostname(value: str) -> str | None:
    parsed = urlparse(value if "://" in value else f"https://{value}")
    hostname = parsed.hostname
    if hostname is None:
        return None
    return hostname.strip().lower()
