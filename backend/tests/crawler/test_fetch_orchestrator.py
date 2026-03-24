from __future__ import annotations

import backend.app.crawler.fetch_orchestrator as fetch_orchestrator_module
import pytest

from backend.app.crawler.fetch_orchestrator import FetchOrchestrator
from backend.app.crawler.content_normalizer import (
    normalize_browser_content,
    normalize_http_content,
)
from backend.app.crawler.error_mapping import map_crawl_failure
from backend.app.crawler.schemas.browser_fetch import BrowserFetchFailure, BrowserFetchSuccess
from backend.app.crawler.schemas.http_fetch import HttpFetchFailure, HttpFetchSuccess
from backend.app.tools.schemas.tool_errors import ToolError, ToolMeta, ToolTimings
from backend.app.tools.schemas.web_crawl import ExtractionResult, NormalizedCrawlContent, WebCrawlError


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


def test_fetch_orchestrator_uses_normalized_http_content_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    fetch_result = HttpFetchSuccess(
        url="https://example.com/article",
        final_url="https://example.com/article",
        status_code=200,
        content_type="text/html",
        body="<html>ignored by patched normalizer</html>",
        meta=_tool_meta(attempts=1, total_ms=12, operation="http_fetch"),
    )
    orchestrator = FetchOrchestrator(
        http_fetch_worker=_HttpWorkerStub(result=fetch_result),
        browser_fetch_worker=_BrowserWorkerUnused(),
    )
    normalized_content = _NonIterableNormalizedContent(
        body="<main>Normalized body</main>",
        content_type="text/html",
    )
    seen: dict[str, str | None] = {"body": None, "content_type": None, "response_body": None}

    monkeypatch.setattr(
        fetch_orchestrator_module,
        "normalize_http_content",
        lambda fetch_result: normalized_content,
    )

    def fake_extract_content(*, body: str, content_type: str, objective: str | None) -> ExtractionResult:
        seen["body"] = body
        seen["content_type"] = content_type
        return ExtractionResult(state="ok", text="Extracted", markdown="Extracted")

    def fake_classify_http_result(*, fetch_result, extraction_result, response_body=None) -> str:
        seen["response_body"] = response_body
        return "success"

    monkeypatch.setattr(fetch_orchestrator_module, "extract_content", fake_extract_content)
    monkeypatch.setattr(fetch_orchestrator_module, "classify_http_result", fake_classify_http_result)

    result = orchestrator.crawl(url="https://example.com/article", objective=None)

    assert seen == {
        "body": "<main>Normalized body</main>",
        "content_type": "text/html",
        "response_body": "<main>Normalized body</main>",
    }
    assert result == fetch_orchestrator_module.CrawlSuccessEnvelope(
        final_url="https://example.com/article",
        status_code=200,
        content_type="text/html",
        extraction_result=ExtractionResult(state="ok", text="Extracted", markdown="Extracted"),
        meta=fetch_result.meta,
        strategy_used="http",
        escalation_count=0,
        session_profile_id=None,
        block_reason=None,
        rendered=False,
        challenge_detected=False,
    )


def test_fetch_orchestrator_maps_non_escalated_http_failure_to_web_crawl_error() -> None:
    orchestrator = FetchOrchestrator(
        http_fetch_worker=_HttpWorkerStub(
            result=HttpFetchFailure(
                url="https://example.com/file.pdf",
                final_url="https://example.com/file.pdf",
                status_code=200,
                content_type="application/pdf",
                error=ToolError(
                    kind="unsupported_content_type",
                    message="unsupported content type: application/pdf",
                    retryable=False,
                    status_code=200,
                    attempt_number=1,
                    operation="http_fetch",
                    timings=ToolTimings(total_ms=17),
                ),
                meta=_tool_meta(attempts=1, total_ms=17, operation="http_fetch"),
            )
        ),
        browser_fetch_worker=_BrowserWorkerUnused(),
    )

    result = orchestrator.crawl(url="https://example.com/file.pdf", objective=None)

    assert isinstance(result, WebCrawlError)
    assert result.error.kind == "unsupported_content_type"
    assert result.error.message == "page content type is unsupported for evidence extraction"
    assert result.error.operation == "web_crawl"
    assert result.meta.operation == "web_crawl"
    assert result.meta.duration_ms == 17


def test_fetch_orchestrator_uses_normalized_browser_content_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    browser_result = BrowserFetchSuccess(
        url="https://example.com/article",
        final_url="https://example.com/article",
        status_code=200,
        content_type="text/html",
        html="<html>ignored by patched normalizer</html>",
        text="ignored",
        rendered=True,
        meta=_tool_meta(attempts=1, total_ms=9, operation="browser_fetch"),
    )
    orchestrator = FetchOrchestrator(
        http_fetch_worker=_HttpWorkerStub(result=_http_success()),
        browser_fetch_worker=_BrowserWorkerStub(result=browser_result),
    )
    normalized_content = _NonIterableNormalizedContent(
        body="<main>Browser normalized body</main>",
        content_type="text/html",
    )
    seen: dict[str, str | None] = {"body": None, "content_type": None, "response_body": None}

    monkeypatch.setattr(
        fetch_orchestrator_module,
        "normalize_browser_content",
        lambda fetch_result: normalized_content,
    )
    monkeypatch.setattr(
        fetch_orchestrator_module,
        "decide_fetch_strategy",
        lambda session_match: _Decision(strategy="browser"),
    )

    def fake_extract_content(*, body: str, content_type: str, objective: str | None) -> ExtractionResult:
        seen["body"] = body
        seen["content_type"] = content_type
        return ExtractionResult(
            state="low-content-quality",
            text="Browser extracted",
            markdown="Browser extracted",
        )

    def fake_classify_http_result(*, fetch_result, extraction_result, response_body=None) -> str:
        seen["response_body"] = response_body
        return "low_content_quality"

    monkeypatch.setattr(fetch_orchestrator_module, "extract_content", fake_extract_content)
    monkeypatch.setattr(fetch_orchestrator_module, "classify_http_result", fake_classify_http_result)

    result = orchestrator.crawl(url="https://example.com/article", objective=None)

    assert seen == {
        "body": "<main>Browser normalized body</main>",
        "content_type": "text/html",
        "response_body": "<main>Browser normalized body</main>",
    }
    assert isinstance(result, WebCrawlError)
    assert result.error.kind == "low_content_quality"
    assert result.error.operation == "web_crawl"


def _tool_meta(*, attempts: int, total_ms: int, operation: str = "web_crawl") -> ToolMeta:
    return ToolMeta(
        operation=operation,
        attempts=attempts,
        retries=max(attempts - 1, 0),
        duration_ms=total_ms,
        timings=ToolTimings(total_ms=total_ms),
    )


class _HttpWorkerStub:
    def __init__(self, *, result: HttpFetchSuccess | HttpFetchFailure) -> None:
        self._result = result

    def fetch(self, *, url: str) -> HttpFetchSuccess | HttpFetchFailure:
        return self._result


class _BrowserWorkerStub:
    def __init__(self, *, result: BrowserFetchSuccess | BrowserFetchFailure) -> None:
        self._result = result

    def fetch(self, *, url: str, session_match) -> BrowserFetchSuccess | BrowserFetchFailure:
        return self._result


class _BrowserWorkerUnused:
    def fetch(self, *, url: str, session_match):
        raise AssertionError("browser worker should not be used in this test")


class _NonIterableNormalizedContent:
    def __init__(self, *, body: str, content_type: str) -> None:
        self.body = body
        self.content_type = content_type


class _Decision:
    def __init__(self, *, strategy: str) -> None:
        self.strategy = strategy


def _http_success() -> HttpFetchSuccess:
    return HttpFetchSuccess(
        url="https://example.com/article",
        final_url="https://example.com/article",
        status_code=200,
        content_type="text/html",
        body="<main>article</main>",
        meta=_tool_meta(attempts=1, total_ms=10, operation="http_fetch"),
    )
