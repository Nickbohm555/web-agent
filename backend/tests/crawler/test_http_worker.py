import httpx
import pytest
from pydantic import ValidationError

from backend.app.schemas.web_crawl import (
    WebCrawlError,
    WebCrawlExcerpt,
    WebCrawlInput,
    WebCrawlSuccess,
)
from backend.app.crawler.http_worker import HttpFetchFailure, HttpFetchSuccess, HttpFetchWorker


def test_web_crawl_input_accepts_absolute_http_urls() -> None:
    payload = WebCrawlInput(url="https://example.com/articles/agent")

    assert str(payload.url) == "https://example.com/articles/agent"


def test_web_crawl_input_accepts_objective() -> None:
    payload = WebCrawlInput(
        url="https://example.com/articles/agent",
        objective=" Find the sections about tool calling. ",
    )

    assert payload.objective == "Find the sections about tool calling."


@pytest.mark.parametrize(
    ("payload", "field_name"),
    [
        ({"url": "example.com"}, "url"),
        ({"url": "ftp://example.com/file.txt"}, "url"),
        (
            {
                "url": "https://example.com/articles/agent",
                "objective": "   ",
            },
            "objective",
        ),
    ],
)
def test_web_crawl_input_rejects_invalid_urls(payload: dict[str, str], field_name: str) -> None:
    with pytest.raises(ValidationError) as exc_info:
        WebCrawlInput(**payload)

    assert field_name in str(exc_info.value)


def test_web_crawl_success_accepts_contract_valid_payload() -> None:
    response = WebCrawlSuccess.model_validate(
        {
            "url": "https://example.com/original",
            "final_url": "https://example.com/final",
            "text": " Main article text ",
            "markdown": " # Main article text ",
            "objective": " Summarize the deployment steps ",
            "excerpts": [
                {
                    "text": " Step 1 installs dependencies. ",
                    "markdown": " - Step 1 installs dependencies. ",
                }
            ],
            "status_code": 200,
            "content_type": " text/html ",
            "fallback_reason": None,
            "meta": {
                "operation": "web_crawl",
                "attempts": 2,
                "retries": 1,
                "duration_ms": 42,
                "timings": {"total_ms": 42},
            },
        }
    )

    assert response.text == "Main article text"
    assert response.markdown == "# Main article text"
    assert response.objective == "Summarize the deployment steps"
    assert response.excerpts == [
        WebCrawlExcerpt(
            text="Step 1 installs dependencies.",
            markdown="- Step 1 installs dependencies.",
        )
    ]
    assert response.content_type == "text/html"


def test_web_crawl_error_accepts_shared_error_envelope() -> None:
    response = WebCrawlError.model_validate(
        {
            "error": {
                "kind": "http_error",
                "message": "origin returned a terminal HTTP status",
                "retryable": False,
                "status_code": 404,
                "operation": "web_crawl",
            },
            "meta": {
                "operation": "web_crawl",
                "attempts": 1,
                "retries": 0,
                "duration_ms": 12,
                "timings": {"total_ms": 12},
            },
        }
    )

    assert response.error.kind == "http_error"
    assert response.meta.operation == "web_crawl"


def test_http_fetch_worker_returns_html_success() -> None:
    client = _mock_http_client(
        lambda request: httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            text="<html><body><article>Hello</article></body></html>",
            request=request,
        )
    )
    result = HttpFetchWorker(http_client=client).fetch(url="https://example.com/page")

    assert isinstance(result, HttpFetchSuccess)
    assert result.status_code == 200
    assert result.final_url == "https://example.com/page"
    assert result.content_type == "text/html"
    assert "Hello" in result.body


def test_http_fetch_worker_captures_final_url_after_redirect() -> None:
    client = _mock_http_client(
        lambda request: (
            httpx.Response(
                302,
                headers={"location": "https://example.com/final"},
                request=request,
            )
            if str(request.url) == "https://example.com/start"
            else httpx.Response(
                200,
                headers={"content-type": "text/html"},
                text="<html><body>Final page</body></html>",
                request=request,
            )
        )
    )
    result = HttpFetchWorker(http_client=client).fetch(url="https://example.com/start")

    assert isinstance(result, HttpFetchSuccess)
    assert result.final_url == "https://example.com/final"
    assert result.meta.attempts == 1


def test_http_fetch_worker_returns_typed_failure_for_unsupported_content_type() -> None:
    client = _mock_http_client(
        lambda request: httpx.Response(
            200,
            headers={"content-type": "application/pdf"},
            content=b"%PDF-1.7",
            request=request,
        )
    )
    result = HttpFetchWorker(http_client=client).fetch(url="https://example.com/file.pdf")

    assert isinstance(result, HttpFetchFailure)
    assert result.error.kind == "unsupported_content_type"
    assert result.error.retryable is False
    assert result.content_type == "application/pdf"


def test_http_fetch_worker_retries_timeout_and_recovers() -> None:
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise httpx.ReadTimeout("timed out", request=request)
        return httpx.Response(
            200,
            headers={"content-type": "text/html"},
            text="<html><body>Recovered</body></html>",
            request=request,
        )

    result = HttpFetchWorker(http_client=_mock_http_client(handler)).fetch(url="https://example.com/slow")

    assert isinstance(result, HttpFetchSuccess)
    assert result.meta.attempts == 3
    assert result.meta.retries == 2
    assert attempts["count"] == 3


def test_http_fetch_worker_classifies_terminal_4xx_without_retry() -> None:
    result = HttpFetchWorker(
        http_client=_mock_http_client(
            lambda request: httpx.Response(
                404,
                headers={"content-type": "text/html"},
                text="<html><body>Missing</body></html>",
                request=request,
            )
        )
    ).fetch(url="https://example.com/missing")

    assert isinstance(result, HttpFetchFailure)
    assert result.error.kind == "http_error"
    assert result.error.retryable is False
    assert result.error.status_code == 404
    assert result.meta.attempts == 1


def _mock_http_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)
