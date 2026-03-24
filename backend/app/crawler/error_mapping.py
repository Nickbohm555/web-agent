from __future__ import annotations

from typing import Optional

from backend.app.crawler.schemas.browser_fetch import BrowserFetchFailure
from backend.app.tools.schemas.tool_errors import ToolError, ToolTimings
from backend.app.tools.schemas.web_crawl import WebCrawlError, WebCrawlMeta


def map_crawl_failure(
    *,
    kind: str,
    message: str,
    total_ms: int,
    retryable: bool,
    status_code: Optional[int] = None,
    attempt_number: int = 1,
    strategy_used: str = "http",
    escalation_count: int = 0,
    session_profile_id: Optional[str] = None,
    block_reason: Optional[str] = None,
    rendered: bool = False,
    challenge_detected: bool = False,
) -> WebCrawlError:
    timings = ToolTimings(total_ms=total_ms)
    return WebCrawlError(
        error=ToolError(
            kind=kind,
            message=message,
            retryable=retryable,
            status_code=status_code,
            attempt_number=attempt_number if retryable else None,
            operation="web_crawl",
            timings=timings,
        ),
        meta=WebCrawlMeta(
            operation="web_crawl",
            attempts=max(attempt_number, 1),
            retries=max(attempt_number - 1, 0),
            duration_ms=total_ms,
            timings=timings,
            strategy_used=strategy_used,
            escalation_count=escalation_count,
            session_profile_id=session_profile_id,
            block_reason=block_reason,
            rendered=rendered,
            challenge_detected=challenge_detected,
        ),
    )


def map_browser_failure(
    failure: BrowserFetchFailure,
    *,
    total_ms: int,
    session_profile_id: Optional[str],
    escalation_count: int,
) -> WebCrawlError:
    return map_crawl_failure(
        kind=failure.error.kind,
        message=failure.error.message,
        total_ms=total_ms,
        retryable=failure.error.retryable,
        status_code=failure.error.status_code,
        attempt_number=failure.error.attempt_number or 1,
        strategy_used="browser",
        escalation_count=escalation_count,
        session_profile_id=session_profile_id,
        rendered=True,
    )
