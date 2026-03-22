from __future__ import annotations

from typing import Any, Sequence
from urllib.parse import urlparse

from pydantic import ValidationError

from backend.agent.schemas import AgentRunRetrievalSearchPolicy
from backend.app.schemas.tool_errors import ToolError, ToolErrorEnvelope, ToolMeta, ToolTimings


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


def is_url_allowed(
    url: str,
    *,
    include_domains: Sequence[str],
    exclude_domains: Sequence[str],
) -> bool:
    """Check whether a URL is allowed by include/exclude domain scope.

    Example input: `is_url_allowed("https://docs.example.com", include_domains=["example.com"], exclude_domains=["blocked.com"])`
    Example output: `True`
    """
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
    """Match a hostname against an exact or subdomain scope.

    Example input: `hostname_matches("docs.example.com", "example.com")`
    Example output: `True`
    """
    return hostname == domain or hostname.endswith(f".{domain}")


def has_domain_scope(
    *,
    include_domains: Sequence[str],
    exclude_domains: Sequence[str],
) -> bool:
    """Return whether any domain restrictions are configured.

    Example input: `has_domain_scope(include_domains=["example.com"], exclude_domains=[])`
    Example output: `True`
    """
    return bool(include_domains or exclude_domains)


def domain_scope_kwargs(search_policy: AgentRunRetrievalSearchPolicy) -> dict[str, list[str]]:
    """Extract include/exclude domain lists from search policy.

    Example input: `domain_scope_kwargs(policy)`
    Example output: `{"include_domains": ["example.com"], "exclude_domains": ["blocked.com"]}`
    """
    return {
        "include_domains": list(search_policy.include_domains),
        "exclude_domains": list(search_policy.exclude_domains),
    }


def normalize_hostname(value: Any) -> str | None:
    """Normalize a hostname from a URL or bare host value.

    Example input: `normalize_hostname("https://Docs.Example.com/page")`
    Example output: `"docs.example.com"`
    """
    normalized_value = str(value)
    parsed = urlparse(
        normalized_value if "://" in normalized_value else f"https://{normalized_value}"
    )
    hostname = parsed.hostname
    if hostname is None:
        return None
    return hostname.strip().lower()
