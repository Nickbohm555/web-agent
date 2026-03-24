from __future__ import annotations

from time import perf_counter
from typing import Any, Callable

from langchain_core.tools import tool
from pydantic import ValidationError

from backend.app.config import get_settings
from backend.app.tools.schemas.web_search import (
    WebSearchError,
    WebSearchInput,
    WebSearchResponse,
    WebSearchToolResult,
)
from backend.app.providers.serper_client import SerperClient, SerperClientError
from backend.app.tools._tool_utils import (
    build_tool_action_error_record,
    build_tool_error_payload,
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
        """Search the web and return typed search results or a typed error."""
        return runner(
            query=query,
            max_results=min(max_results, bounded_cap),
        )

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
        del freshness
        response = (client or create_serper_client()).search(
            query=validated_input.query,
            max_results=validated_input.max_results,
        )
        return WebSearchResponse.model_validate(response)
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
