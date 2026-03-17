from __future__ import annotations

from time import perf_counter
from typing import Any

from langchain_core.tools import tool
from pydantic import ValidationError

from backend.app.config import get_settings
from backend.app.contracts.tool_errors import ToolError, ToolErrorEnvelope, ToolMeta, ToolTimings
from backend.app.contracts.web_search import WebSearchInput, WebSearchResponse
from backend.app.providers.serper_client import SerperClient, SerperClientError


def create_serper_client() -> SerperClient:
    return SerperClient(api_key=get_settings().SERPER_API_KEY)


def run_web_search(
    *,
    query: str,
    max_results: int = 5,
    client: SerperClient | None = None,
) -> dict[str, Any]:
    operation_start = perf_counter()
    try:
        validated_input = WebSearchInput(query=query, max_results=max_results)
        response = (client or create_serper_client()).search(
            query=validated_input.query,
            max_results=validated_input.max_results,
        )
        validated_response = WebSearchResponse.model_validate(response)
        return validated_response.model_dump(mode="json")
    except ValidationError as exc:
        total_ms = _elapsed_ms(operation_start)
        return ToolErrorEnvelope(
            error=ToolError(
                kind="invalid_request",
                message=_validation_error_message(exc),
                retryable=False,
                attempt_number=1,
                operation="web_search",
                timings=ToolTimings(total_ms=total_ms),
            ),
            meta=ToolMeta(
                operation="web_search",
                attempts=1,
                retries=0,
                duration_ms=total_ms,
                timings=ToolTimings(total_ms=total_ms),
            ),
        ).model_dump(mode="json")
    except SerperClientError as exc:
        total_ms = _elapsed_ms(operation_start)
        attempts = exc.attempt_number or 1
        timings = ToolTimings(total_ms=total_ms, provider_ms=exc.provider_ms)
        return ToolErrorEnvelope(
            error=ToolError(
                kind=exc.kind,
                message=exc.message,
                retryable=exc.retryable,
                status_code=exc.status_code,
                attempt_number=attempts,
                operation=exc.operation,
                timings=timings,
            ),
            meta=ToolMeta(
                operation=exc.operation,
                attempts=attempts,
                retries=max(attempts - 1, 0),
                duration_ms=total_ms,
                timings=timings,
            ),
        ).model_dump(mode="json")
    except Exception:
        total_ms = _elapsed_ms(operation_start)
        return ToolErrorEnvelope(
            error=ToolError(
                kind="internal_error",
                message="unexpected web_search failure",
                retryable=False,
                attempt_number=1,
                operation="web_search",
                timings=ToolTimings(total_ms=total_ms),
            ),
            meta=ToolMeta(
                operation="web_search",
                attempts=1,
                retries=0,
                duration_ms=total_ms,
                timings=ToolTimings(total_ms=total_ms),
            ),
        ).model_dump(mode="json")


@tool("web_search", args_schema=WebSearchInput)
def web_search(query: str, max_results: int = 5) -> dict[str, Any]:
    """Search the web and return normalized results or a structured error envelope."""
    return run_web_search(query=query, max_results=max_results)


def _elapsed_ms(start: float) -> int:
    return int((perf_counter() - start) * 1000)


def _validation_error_message(exc: ValidationError) -> str:
    first_error = exc.errors()[0]
    location = ".".join(str(part) for part in first_error.get("loc", []))
    if location:
        return f"{location}: {first_error['msg']}"
    return str(exc)
