from __future__ import annotations

from backend.app.crawler.fetch_strategy import (
    classify_http_result,
    decide_fetch_strategy,
    should_escalate_http_result,
)
from backend.app.crawler.schemas.fetch_strategy import FetchClassification
from backend.app.crawler.schemas.http_fetch import HttpFetchFailure
from backend.app.crawler.schemas.session_profile import (
    DomainSessionMatch,
    SessionProfile,
)
from backend.app.tools.schemas.tool_errors import ToolError, ToolMeta, ToolTimings
from backend.app.tools.schemas.web_crawl import ExtractionResult


def test_decide_fetch_strategy_defaults_to_http_without_session_profile() -> None:
    decision = decide_fetch_strategy(session_match=None)

    assert decision.strategy == "http"
    assert decision.escalation_reason is None


def test_decide_fetch_strategy_starts_in_browser_for_browser_only_profile() -> None:
    decision = decide_fetch_strategy(
        session_match=DomainSessionMatch(
            matched_domain="app.example.com",
            profile=SessionProfile(
                id="browser-profile",
                domains=["app.example.com"],
                browser_only=True,
            ),
        )
    )

    assert decision.strategy == "browser"
    assert decision.escalation_reason == "browser_required"


def test_should_escalate_http_result_for_terminal_auth_status() -> None:
    failure = HttpFetchFailure(
        url="https://example.com/protected",
        final_url="https://example.com/login",
        status_code=403,
        content_type="text/html",
        error=ToolError(
            kind="http_error",
            message="origin returned a terminal HTTP status",
            retryable=False,
            status_code=403,
            attempt_number=1,
            operation="web_crawl",
            timings=ToolTimings(total_ms=80),
        ),
        meta=ToolMeta(
            operation="web_crawl",
            attempts=1,
            retries=0,
            duration_ms=80,
            timings=ToolTimings(total_ms=80),
        ),
    )

    classification = classify_http_result(fetch_result=failure, extraction_result=None)

    assert classification == "blocked"
    assert should_escalate_http_result(classification=classification) == "http_403"


def test_classify_http_result_marks_low_content_as_javascript_required_when_shell_like() -> None:
    extraction_result = ExtractionResult(
        state="low-content-quality",
        text="Enable JavaScript to run this app.",
        markdown="Enable JavaScript to run this app.",
        excerpts=[],
        fallback_reason="low-content-quality",
    )

    classification = classify_http_result(
        fetch_result=None,
        extraction_result=extraction_result,
        response_body="<html><body><div id='root'></div><script src='/app.js'></script></body></html>",
    )

    assert classification == "javascript_required"
    assert should_escalate_http_result(classification=classification) == "javascript_required"
