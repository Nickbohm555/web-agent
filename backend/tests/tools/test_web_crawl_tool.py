import importlib

import httpx

from backend.app.contracts.web_crawl import WebCrawlError, WebCrawlSuccess
from backend.app.crawler.http_worker import HttpFetchWorker
from backend.app.tools.web_crawl import run_web_crawl, web_crawl


web_crawl_module = importlib.import_module("backend.app.tools.web_crawl")


def test_web_crawl_tool_invokes_successful_extraction(monkeypatch) -> None:
    worker = HttpFetchWorker(http_client=_mock_http_client(_rich_article_handler))
    monkeypatch.setattr(web_crawl_module, "create_http_fetch_worker", lambda: worker)

    payload = web_crawl.invoke({"url": "https://example.com/article"})
    result = WebCrawlSuccess.model_validate(payload)

    assert web_crawl.name == "web_crawl"
    assert str(result.url) == "https://example.com/article"
    assert str(result.final_url) == "https://example.com/article"
    assert result.fallback_reason is None
    assert "agent systems" in result.text.lower()
    assert result.markdown


def test_run_web_crawl_preserves_redirect_final_url() -> None:
    worker = HttpFetchWorker(http_client=_mock_http_client(_redirect_handler))

    payload = run_web_crawl(url="https://example.com/start", fetch_worker=worker)
    result = WebCrawlSuccess.model_validate(payload)

    assert str(result.url) == "https://example.com/start"
    assert str(result.final_url) == "https://example.com/final"
    assert result.meta.attempts == 1
    assert result.fallback_reason is None


def test_run_web_crawl_returns_success_fallback_for_unsupported_content_type() -> None:
    worker = HttpFetchWorker(http_client=_mock_http_client(_pdf_handler))

    payload = run_web_crawl(url="https://example.com/file.pdf", fetch_worker=worker)
    result = WebCrawlSuccess.model_validate(payload)

    assert result.status_code == 200
    assert result.content_type == "application/pdf"
    assert result.fallback_reason == "unsupported-content-type"
    assert result.text == ""
    assert result.markdown == ""


def test_run_web_crawl_returns_success_fallback_for_low_content_quality() -> None:
    worker = HttpFetchWorker(http_client=_mock_http_client(_boilerplate_handler))

    payload = run_web_crawl(url="https://example.com/thin", fetch_worker=worker)
    result = WebCrawlSuccess.model_validate(payload)

    assert result.status_code == 200
    assert result.content_type == "text/html"
    assert result.fallback_reason == "low-content-quality"
    assert result.text == ""
    assert result.markdown == ""


def test_run_web_crawl_returns_structured_retryable_error_metadata() -> None:
    worker = HttpFetchWorker(http_client=_mock_http_client(_retryable_failure_handler))

    payload = run_web_crawl(url="https://example.com/unavailable", fetch_worker=worker)
    result = WebCrawlError.model_validate(payload)

    assert result.error.kind == "http_error"
    assert result.error.retryable is True
    assert result.error.status_code == 503
    assert result.error.attempt_number == 3
    assert result.error.operation == "web_crawl"
    assert result.meta.attempts == 3
    assert result.meta.retries == 2


def _mock_http_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True)


def _rich_article_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        headers={"content-type": "text/html; charset=utf-8"},
        text=_rich_article_html(),
        request=request,
    )


def _redirect_handler(request: httpx.Request) -> httpx.Response:
    if str(request.url) == "https://example.com/start":
        return httpx.Response(
            302,
            headers={"location": "https://example.com/final"},
            request=request,
        )

    return httpx.Response(
        200,
        headers={"content-type": "text/html"},
        text=_rich_article_html(),
        request=request,
    )


def _pdf_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        headers={"content-type": "application/pdf"},
        content=b"%PDF-1.7",
        request=request,
    )


def _boilerplate_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        headers={"content-type": "text/html"},
        text="""
        <html>
          <body>
            <header>Home Docs Login</header>
            <nav>Products Pricing About</nav>
            <footer>Copyright Example</footer>
          </body>
        </html>
        """,
        request=request,
    )


def _retryable_failure_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        503,
        headers={"content-type": "text/html"},
        text="<html><body>try again later</body></html>",
        request=request,
    )


def _rich_article_html() -> str:
    paragraphs = [
        "Agent systems need consistent retrieval contracts so orchestration layers can reason about success and failure without leaking provider payloads.",
        "A high quality extraction should preserve the main narrative, remove navigation chrome, and produce enough text for downstream summarization and answer synthesis.",
        "Deterministic quality thresholds keep crawl behavior debuggable by ensuring weak pages become explicit fallback states instead of silent empty successes.",
    ]
    article = "".join(f"<p>{paragraph}</p>" for paragraph in paragraphs)
    return f"""
    <html>
      <body>
        <header><nav>Home Docs Pricing</nav></header>
        <main>
          <article>
            <h1>Reliable agent systems</h1>
            {article}
          </article>
        </main>
        <footer>Footer links and contact info</footer>
      </body>
    </html>
    """
