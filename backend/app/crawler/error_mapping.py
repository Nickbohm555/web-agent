from __future__ import annotations

from backend.app.crawler.fetch_classification import classify_http_result
from backend.app.crawler.schemas.browser_fetch import BrowserFetchFailure
from backend.app.crawler.schemas.fetch_strategy import FetchClassification
from backend.app.crawler.schemas.http_fetch import HttpFetchFailure
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


def map_crawl_failure(
    fetch_result: HttpFetchFailure | BrowserFetchFailure,
    *,
    total_ms: int | None = None,
    attempt_number: int | None = None,
) -> WebCrawlError:
    effective_total_ms = fetch_result.meta.duration_ms if total_ms is None else total_ms
    effective_attempt_number = fetch_result.meta.attempts if attempt_number is None else attempt_number
    if isinstance(fetch_result, HttpFetchFailure):
        if fetch_result.error.retryable:
            envelope = build_tool_error_payload(
                kind=fetch_result.error.kind,
                message=fetch_result.error.message,
                retryable=True,
                total_ms=effective_total_ms,
                operation="web_crawl",
                status_code=fetch_result.status_code,
                attempt_number=effective_attempt_number,
            )
            return WebCrawlError(error=envelope.error, meta=envelope.meta)
        classification = classify_http_result(fetch_result=fetch_result, extraction_result=None)
        return map_classification_error(
            kind=classification,
            total_ms=effective_total_ms,
            status_code=fetch_result.status_code,
            attempt_number=effective_attempt_number,
            retryable=fetch_result.error.retryable,
        )

    return map_classification_error(
        kind="browser_navigation_failed",
        total_ms=effective_total_ms,
        status_code=fetch_result.status_code,
        attempt_number=effective_attempt_number,
        message=fetch_result.error.message,
        retryable=fetch_result.error.retryable,
    )


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
