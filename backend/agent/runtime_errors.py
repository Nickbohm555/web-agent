from __future__ import annotations

from time import perf_counter

from pydantic import ValidationError

from backend.agent.runtime_constants import (
    QUICK_SEARCH_ERROR_CATEGORY_BY_KIND,
    QUICK_SEARCH_ERROR_MESSAGE_BY_KIND,
)
from backend.agent.types import AgentRunError, AgentRunResult
from backend.app.contracts.tool_errors import ToolErrorEnvelope


def coerce_tool_error(payload: object) -> ToolErrorEnvelope | None:
    if not isinstance(payload, dict) or "error" not in payload:
        return None
    return ToolErrorEnvelope.model_validate(payload)


def map_quick_search_error_category(kind: str) -> str:
    return QUICK_SEARCH_ERROR_CATEGORY_BY_KIND.get(kind, "tool_failure")


def map_quick_search_error_message(kind: str) -> str:
    return QUICK_SEARCH_ERROR_MESSAGE_BY_KIND.get(kind, "quick search failed")


def map_runtime_failure(*, exc: Exception, run_id: str, started_at: float) -> AgentRunResult:
    category = "internal_error"
    retryable = False
    message = "agent runtime failed"

    if is_recursion_limit_error(exc):
        category = "loop_limit"
        message = "agent exceeded bounded execution limit"
    elif is_timeout_error(exc):
        category = "timeout"
        retryable = True
        message = "agent execution timed out"
    elif is_tool_runtime_error(exc):
        category = "tool_failure"
        message = "agent tool invocation failed"
    elif is_provider_runtime_error(exc):
        category = "provider_failure"
        retryable = True
        message = "agent provider request failed"
    elif isinstance(exc, ValidationError):
        category = "invalid_prompt"
        message = first_validation_error(exc) or "prompt is invalid"
    elif isinstance(exc, ValueError):
        category = "invalid_prompt"
        message = str(exc) or "prompt is invalid"

    return failed_result(
        run_id=run_id,
        started_at=started_at,
        category=category,
        message=message,
        retryable=retryable,
    )


def failed_result(
    *,
    run_id: str,
    started_at: float,
    category: str,
    message: str,
    retryable: bool,
) -> AgentRunResult:
    return AgentRunResult(
        run_id=run_id,
        status="failed",
        final_answer="",
        tool_call_count=0,
        elapsed_ms=elapsed_ms(started_at),
        error=AgentRunError(
            category=category,
            message=message,
            retryable=retryable,
        ),
    )


def elapsed_ms(started_at: float) -> int:
    return int((perf_counter() - started_at) * 1000)


def first_validation_error(exc: ValidationError) -> str | None:
    errors = exc.errors()
    if not errors:
        return None

    message = errors[0].get("msg")
    if not isinstance(message, str):
        return None

    prefix = "Value error, "
    if message.startswith(prefix):
        return message[len(prefix) :]
    return message


def is_recursion_limit_error(exc: Exception) -> bool:
    name = type(exc).__name__.lower()
    message = str(exc).lower()
    return "graphrecursion" in name or "recursion" in message


def is_timeout_error(exc: Exception) -> bool:
    try:
        import httpx
    except Exception:
        httpx = None  # type: ignore[assignment]

    timeout_types: tuple[type[BaseException], ...] = (TimeoutError,)
    if httpx is not None:
        timeout_types = timeout_types + (httpx.TimeoutException,)
    return isinstance(exc, timeout_types)


def is_tool_runtime_error(exc: Exception) -> bool:
    name = type(exc).__name__.lower()
    message = str(exc).lower()
    return "tool" in name or "tool" in message


def is_provider_runtime_error(exc: Exception) -> bool:
    try:
        import httpx
    except Exception:
        httpx = None  # type: ignore[assignment]

    if httpx is not None and isinstance(exc, httpx.HTTPError):
        return True

    name = type(exc).__name__.lower()
    return any(token in name for token in ("openai", "provider", "api", "rate", "auth"))
