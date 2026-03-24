from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from backend.app.tools.schemas.tool_errors import ToolError, ToolErrorEnvelope, ToolMeta, ToolTimings


def validation_error_message(exc: ValidationError) -> str:
    """Extract the first Pydantic validation error as a stable message.

    Example input: `validation_error_message(exc)`
    Example output: `"query: Input should have at least 1 character"`
    """
    first_error = exc.errors()[0]
    location = ".".join(str(part) for part in first_error.get("loc", []))
    if location:
        return f"{location}: {first_error['msg']}"
    return str(exc)


def build_tool_error_payload(
    *,
    kind: str,
    message: str,
    retryable: bool,
    total_ms: int,
    operation: str,
    status_code: int | None = None,
    attempt_number: int = 1,
    provider_ms: int | None = None,
) -> ToolErrorEnvelope:
    """Build the shared typed tool error envelope.

    Example input: `build_tool_error_payload(kind="invalid_request", message="bad input", retryable=False, total_ms=3, operation="web_search")`
    Example output: `ToolErrorEnvelope(error=ToolError(kind="invalid_request", ...), ...)`
    """
    timings = ToolTimings(total_ms=total_ms, provider_ms=provider_ms)
    return ToolErrorEnvelope(
        error=ToolError(
            kind=kind,
            message=message,
            retryable=retryable,
            status_code=status_code,
            attempt_number=attempt_number,
            operation=operation,
            timings=timings,
        ),
        meta=ToolMeta(
            operation=operation,
            attempts=attempt_number,
            retries=max(attempt_number - 1, 0),
            duration_ms=total_ms,
            timings=timings,
        ),
    )


def build_tool_action_error_record(
    *,
    action_type: str,
    subject_key: str,
    subject_value: str,
    payload: Any,
) -> dict[str, Any] | None:
    """Convert a typed tool error payload into an action-log record.

    Example input: `build_tool_action_error_record(action_type="search", subject_key="query", subject_value="agents", payload=ToolErrorEnvelope(...))`
    Example output: `{"action_type": "search", "query": "agents", "error_kind": "invalid_request", ...}`
    """
    try:
        envelope = ToolErrorEnvelope.model_validate(payload)
    except ValidationError:
        return None

    action_record: dict[str, Any] = {
        "action_type": action_type,
        subject_key: subject_value,
        "error_kind": envelope.error.kind,
        "message": envelope.error.message,
        "retryable": envelope.error.retryable,
    }
    action_record["attempts"] = envelope.meta.attempts
    if envelope.error.status_code is not None:
        action_record["status_code"] = envelope.error.status_code
    return action_record

