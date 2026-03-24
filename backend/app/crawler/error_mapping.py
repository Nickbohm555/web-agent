from __future__ import annotations

from backend.app.crawler.schemas.fetch_strategy import FetchClassification
from backend.app.tools._tool_utils import build_tool_error_payload
from backend.app.tools.schemas.web_crawl import WebCrawlError

_DEFAULT_MESSAGES: dict[FetchClassification, str] = {
    "auth_required": "page requires authenticated session state",
    "blocked": "page blocked non-browser retrieval",
    "browser_navigation_failed": "browser navigation failed before evidence was recovered",
    "challenge_detected": "page presented a challenge instead of content",
    "javascript_required": "page requires browser rendering before content is available",
    "low_content_quality": "page did not yield enough evidence after retrieval attempts",
    "network_error": "request failed before evidence was recovered",
    "session_profile_misconfigured": "stored session profile could not be applied",
    "success": "page retrieval unexpectedly reported success without evidence",
    "unsupported_content_type": "page content type is unsupported for evidence extraction",
}


def map_classification_error(
    *,
    kind: FetchClassification,
    total_ms: int,
    status_code: int | None = None,
    attempt_number: int = 1,
    message: str | None = None,
    retryable: bool = False,
) -> WebCrawlError:
    envelope = build_tool_error_payload(
        kind=kind,
        message=message or _DEFAULT_MESSAGES[kind],
        retryable=retryable,
        total_ms=total_ms,
        operation="web_crawl",
        status_code=status_code,
        attempt_number=attempt_number,
    )
    return WebCrawlError(error=envelope.error, meta=envelope.meta)
