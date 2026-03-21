from __future__ import annotations

from time import perf_counter
from typing import Any, Callable

from langchain_core.tools import tool
from pydantic import ValidationError

from backend.agent.types import (
    AgentRunRetrievalPolicy,
    AgentRunRetrievalSearchPolicy,
)
from backend.app.config import get_settings
from backend.app.contracts.web_search import WebSearchInput, WebSearchResponse
from backend.app.providers.serper_client import SerperClient, SerperClientError
from backend.app.tools._tool_utils import (
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
    search_policy: AgentRunRetrievalSearchPolicy,
) -> str:
    include_terms = [
        f"site:{domain}" for domain in search_policy.include_domains
    ]
    exclude_terms = [
        f"-site:{domain}" for domain in search_policy.exclude_domains
    ]
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

    error = payload.get("error")
    meta = payload.get("meta")
    if isinstance(error, dict):
        action_record = {
            "action_type": "search",
            "query": normalized_query,
            "error_kind": error.get("kind"),
            "message": error.get("message"),
            "retryable": error.get("retryable"),
        }
        if isinstance(meta, dict):
            action_record["attempts"] = meta.get("attempts")
        if error.get("status_code") is not None:
            action_record["status_code"] = error.get("status_code")
        return action_record

    return {
        "action_type": "search",
        "query": normalized_query,
    }
