from __future__ import annotations

from backend.app.crawler.content_normalizer import (
    normalize_browser_content,
    normalize_http_content,
)
from backend.app.crawler.error_mapping import map_crawl_failure
from backend.app.crawler.schemas.browser_fetch import BrowserFetchFailure, BrowserFetchSuccess
from backend.app.crawler.schemas.http_fetch import HttpFetchFailure, HttpFetchSuccess
from backend.app.tools.schemas.tool_errors import ToolError, ToolMeta, ToolTimings
from backend.app.tools.schemas.web_crawl import NormalizedCrawlContent, WebCrawlError


def test_normalize_http_content_returns_shared_content_model() -> None:
    result = normalize_http_content(
        HttpFetchSuccess(
            url="https://example.com/start",
            final_url="https://example.com/final",
            status_code=200,
            content_type="text/html",
            body="<html><body>Article</body></html>",
            meta=_tool_meta(attempts=1, total_ms=12),
        )
    )

    assert isinstance(result, NormalizedCrawlContent)
    assert result.source == "http"
    assert result.body == "<html><body>Article</body></html>"
    assert result.content_type == "text/html"
    assert result.rendered is False
    assert tuple(result) == ("<html><body>Article</body></html>", "text/html")


def test_normalize_browser_content_prefers_html_and_falls_back_to_text() -> None:
    html_result = normalize_browser_content(
        BrowserFetchSuccess(
            url="https://example.com/article",
            final_url="https://example.com/article",
            status_code=200,
            content_type="text/html",
            html="  <main>Rendered</main>  ",
            text="Rendered",
            rendered=True,
            meta=_tool_meta(attempts=1, total_ms=20),
        )
    )
    text_result = normalize_browser_content(
        BrowserFetchSuccess(
            url="https://example.com/article",
            final_url="https://example.com/article",
            status_code=200,
            content_type="text/html",
            html="   ",
            text="  Plain text fallback  ",
            rendered=True,
            meta=_tool_meta(attempts=1, total_ms=20),
        )
    )

    assert isinstance(html_result, NormalizedCrawlContent)
    assert html_result.source == "browser"
    assert html_result.body == "<main>Rendered</main>"
    assert html_result.rendered is True
    assert html_result.raw_html == "<main>Rendered</main>"
    assert html_result.extracted_text == "Rendered"

    assert isinstance(text_result, NormalizedCrawlContent)
    assert text_result.body == "Plain text fallback"
    assert text_result.raw_html is None
    assert text_result.extracted_text == "Plain text fallback"
    assert tuple(text_result) == ("Plain text fallback", "text/html")


def test_map_crawl_failure_maps_http_failure_to_typed_error() -> None:
    result = map_crawl_failure(
        HttpFetchFailure(
            url="https://example.com/protected",
            final_url="https://example.com/protected",
            status_code=401,
            content_type="text/html",
            error=ToolError(
                kind="http_error",
                message="login required",
                retryable=False,
                status_code=401,
                attempt_number=1,
                operation="http_fetch",
                timings=ToolTimings(total_ms=33),
            ),
            meta=_tool_meta(attempts=1, total_ms=33, operation="http_fetch"),
        )
    )

    assert isinstance(result, WebCrawlError)
    assert result.error.kind == "auth_required"
    assert result.error.message == "page requires authenticated session state"
    assert result.error.retryable is False
    assert result.error.status_code == 401
    assert result.error.operation == "web_crawl"
    assert result.meta.operation == "web_crawl"
    assert result.meta.duration_ms == 33


def test_map_crawl_failure_maps_browser_failure_to_typed_error() -> None:
    result = map_crawl_failure(
        BrowserFetchFailure(
            url="https://example.com/article",
            final_url="https://example.com/article",
            status_code=504,
            content_type="text/html",
            navigation_error_kind="timeout",
            error=ToolError(
                kind="browser_timeout",
                message="navigation timed out",
                retryable=True,
                status_code=504,
                attempt_number=2,
                operation="browser_fetch",
                timings=ToolTimings(total_ms=200),
            ),
            meta=_tool_meta(attempts=2, total_ms=200, operation="browser_fetch"),
            rendered=True,
        )
    )

    assert isinstance(result, WebCrawlError)
    assert result.error.kind == "browser_navigation_failed"
    assert result.error.message == "navigation timed out"
    assert result.error.retryable is True
    assert result.error.status_code == 504
    assert result.error.attempt_number == 2
    assert result.error.operation == "web_crawl"
    assert result.meta.attempts == 2
    assert result.meta.retries == 1


def _tool_meta(*, attempts: int, total_ms: int, operation: str = "web_crawl") -> ToolMeta:
    return ToolMeta(
        operation=operation,
        attempts=attempts,
        retries=max(attempts - 1, 0),
        duration_ms=total_ms,
        timings=ToolTimings(total_ms=total_ms),
    )
