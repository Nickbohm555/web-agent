from __future__ import annotations

from typing import Any, Sequence
from urllib.parse import urlparse

from pydantic import ValidationError

from backend.agent.types import AgentRunRetrievalSearchPolicy
from backend.app.contracts.tool_errors import ToolError, ToolErrorEnvelope, ToolMeta, ToolTimings


def validation_error_message(exc: ValidationError) -> str:
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
) -> dict[str, Any]:
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
    ).model_dump(mode="json")


def build_tool_action_error_record(
    *,
    action_type: str,
    subject_key: str,
    subject_value: str,
    payload: dict[str, Any],
) -> dict[str, Any] | None:
    error = payload.get("error")
    if not isinstance(error, dict):
        return None

    action_record: dict[str, Any] = {
        "action_type": action_type,
        subject_key: subject_value,
        "error_kind": error.get("kind"),
        "message": error.get("message"),
        "retryable": error.get("retryable"),
    }
    meta = payload.get("meta")
    if isinstance(meta, dict):
        action_record["attempts"] = meta.get("attempts")
    if error.get("status_code") is not None:
        action_record["status_code"] = error.get("status_code")
    return action_record


def is_url_allowed(
    url: str,
    *,
    include_domains: Sequence[str],
    exclude_domains: Sequence[str],
) -> bool:
    if not has_domain_scope(
        include_domains=include_domains,
        exclude_domains=exclude_domains,
    ):
        return True

    hostname = normalize_hostname(url)
    if hostname is None:
        return False

    if any(hostname_matches(hostname, blocked) for blocked in exclude_domains):
        return False

    if not include_domains:
        return True

    return any(hostname_matches(hostname, allowed) for allowed in include_domains)


def hostname_matches(hostname: str, domain: str) -> bool:
    return hostname == domain or hostname.endswith(f".{domain}")


def has_domain_scope(
    *,
    include_domains: Sequence[str],
    exclude_domains: Sequence[str],
) -> bool:
    return bool(include_domains or exclude_domains)


def domain_scope_kwargs(search_policy: AgentRunRetrievalSearchPolicy) -> dict[str, list[str]]:
    return {
        "include_domains": list(search_policy.include_domains),
        "exclude_domains": list(search_policy.exclude_domains),
    }


def normalize_hostname(value: Any) -> str | None:
    normalized_value = str(value)
    parsed = urlparse(
        normalized_value if "://" in normalized_value else f"https://{normalized_value}"
    )
    hostname = parsed.hostname
    if hostname is None:
        return None
    return hostname.strip().lower()
