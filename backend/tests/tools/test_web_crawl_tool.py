import importlib

import httpx
import pytest
from pydantic import ValidationError

from backend.agent.schemas import AgentRunRetrievalPolicy
from backend.app.tools.schemas.tool_errors import ToolError, ToolMeta, ToolTimings
from backend.app.tools.schemas.web_crawl import WebCrawlError, WebCrawlSuccess, WebCrawlToolInput
from backend.app.tools.schemas.web_crawl_batch import WebCrawlBatchSuccess
from backend.app.crawler.http_worker import HttpFetchWorker
from backend.app.tools.web_crawl import (
    build_web_crawl_action_record,
    build_web_crawl_tool,
    open_url,
    run_web_crawl,
    web_crawl,
)


web_crawl_module = importlib.import_module("backend.app.tools.web_crawl")


def test_web_crawl_input_accepts_single_url_and_objective() -> None:
    model = WebCrawlToolInput(url="https://example.com/article", objective="Find pricing")

    assert str(model.url) == "https://example.com/article"
    assert model.objective == "Find pricing"


def test_web_crawl_tool_input_accepts_urls_and_rejects_url_plus_urls() -> None:
    with pytest.raises(ValidationError):
        WebCrawlToolInput(
            url="https://example.com/a",
            urls=["https://example.com/b"],
        )


def test_web_crawl_tool_input_rejects_missing_url_and_urls() -> None:
    with pytest.raises(ValidationError):
        WebCrawlToolInput()


def test_web_crawl_tool_input_rejects_more_than_five_urls() -> None:
    with pytest.raises(ValidationError):
        WebCrawlToolInput(urls=[f"https://example.com/{index}" for index in range(6)])


def test_web_crawl_batch_success_preserves_input_order() -> None:
    payload = WebCrawlBatchSuccess.model_validate(
        {
            "requested_urls": ["https://example.com/a", "https://example.com/b"],
            "items": [
                {
                    "url": "https://example.com/a",
                    "status": "succeeded",
                    "result": {
                        "url": "https://example.com/a",
                        "final_url": "https://example.com/a",
                        "text": "alpha",
                        "markdown": "alpha",
                        "objective": None,
                        "excerpts": [],
                        "status_code": 200,
                        "content_type": "text/html",
                        "fallback_reason": None,
                        "meta": {
                            "operation": "web_crawl",
                            "attempts": 1,
                            "retries": 0,
                            "duration_ms": 10,
                            "timings": {"total_ms": 10},
                        },
                    },
                    "error": None,
                },
                {
                    "url": "https://example.com/b",
                    "status": "failed",
                    "result": None,
                    "error": {
                        "kind": "invalid_request",
                        "message": "blocked",
                        "retryable": False,
                        "status_code": None,
                        "attempt_number": None,
                        "operation": "web_crawl",
                        "timings": {"total_ms": 4},
                    },
                },
            ],
            "meta": {
                "operation": "web_crawl",
                "attempts": 2,
                "retries": 0,
                "duration_ms": 14,
                "timings": {"total_ms": 14},
            },
            "summary": {"attempted": 2, "succeeded": 1, "failed": 1},
        }
    )

    assert [str(item.url) for item in payload.items] == [
        "https://example.com/a",
        "https://example.com/b",
    ]


def test_web_crawl_tool_invokes_successful_extraction(monkeypatch) -> None:
    worker = HttpFetchWorker(http_client=_mock_http_client(_rich_article_handler))
    monkeypatch.setattr(web_crawl_module, "create_http_fetch_worker", lambda: worker)

    payload = open_url.invoke({"url": "https://example.com/article"})
    result = WebCrawlSuccess.model_validate(payload)

    assert open_url.name == "open_url"
    assert web_crawl is open_url
    assert str(result.url) == "https://example.com/article"
    assert str(result.final_url) == "https://example.com/article"
    assert result.fallback_reason is None
    assert "agent systems" in result.text.lower()
    assert result.markdown


def test_web_crawl_tool_accepts_objective_and_preserves_contract(monkeypatch) -> None:
    worker = HttpFetchWorker(http_client=_mock_http_client(_rich_article_handler))
    monkeypatch.setattr(web_crawl_module, "create_http_fetch_worker", lambda: worker)

    payload = web_crawl.invoke(
        {
            "url": "https://example.com/article",
            "objective": "Find the sections about agent systems",
        }
    )
    result = WebCrawlSuccess.model_validate(payload)

    assert result.objective == "Find the sections about agent systems"
    assert result.excerpts
    assert "agent systems" in result.excerpts[0].text.lower()
    assert "agent systems" in result.text.lower()


def test_web_crawl_tool_uses_lead_excerpt_when_objective_has_no_clear_match(monkeypatch) -> None:
    worker = HttpFetchWorker(http_client=_mock_http_client(_rich_article_handler))
    monkeypatch.setattr(web_crawl_module, "create_http_fetch_worker", lambda: worker)

    payload = web_crawl.invoke(
        {
            "url": "https://example.com/article",
            "objective": "Find the unrelated pricing calculator details",
        }
    )
    result = WebCrawlSuccess.model_validate(payload)

    assert result.excerpts
    assert "consistent retrieval contracts" in result.excerpts[0].text.lower()


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


def test_web_crawl_batch_returns_ordered_mixed_results(monkeypatch) -> None:
    worker = HttpFetchWorker(http_client=_mock_http_client(_batch_mixed_handler))
    monkeypatch.setattr(web_crawl_module, "create_http_fetch_worker", lambda: worker)

    payload = web_crawl.invoke(
        {"urls": ["https://example.com/a", "https://example.com/b"]}
    )
    result = WebCrawlBatchSuccess.model_validate(payload)

    assert result.summary.attempted == 2
    assert [item.status for item in result.items] == ["succeeded", "failed"]


def test_web_crawl_batch_preserves_fallback_success_for_pdf(monkeypatch) -> None:
    worker = HttpFetchWorker(http_client=_mock_http_client(_pdf_handler))
    monkeypatch.setattr(web_crawl_module, "create_http_fetch_worker", lambda: worker)

    payload = web_crawl.invoke({"urls": ["https://example.com/file.pdf"]})
    result = WebCrawlBatchSuccess.model_validate(payload)

    assert result.items[0].result is not None
    assert result.items[0].result.fallback_reason == "unsupported-content-type"


def test_web_crawl_batch_returns_per_item_invalid_request_for_policy_blocked_url(
    monkeypatch,
) -> None:
    worker = HttpFetchWorker(http_client=_mock_http_client(_rich_article_handler))
    monkeypatch.setattr(web_crawl_module, "create_http_fetch_worker", lambda: worker)
    tool_instance = build_web_crawl_tool(
        retrieval_policy=AgentRunRetrievalPolicy.model_validate(
            {"search": {"include_domains": ["example.com"]}}
        )
    )

    payload = tool_instance.invoke(
        {"urls": ["https://example.com/a", "https://blocked.com/b"]}
    )
    result = WebCrawlBatchSuccess.model_validate(payload)

    assert result.items[1].status == "failed"
    assert result.items[1].error is not None
    assert result.items[1].error.kind == "invalid_request"


def test_build_web_crawl_action_record_summarizes_success_payload() -> None:
    record = build_web_crawl_action_record(
        url="https://example.com/article",
        payload={
            "url": "https://example.com/article",
            "final_url": "https://example.com/final",
            "text": "A concise extracted summary of the page body.",
            "markdown": "A concise extracted summary of the page body.",
            "objective": "Find the summary",
            "excerpts": [
                {
                    "text": "Focused excerpt for the summary.",
                    "markdown": "Focused excerpt for the summary.",
                }
            ],
            "status_code": 200,
            "content_type": "text/html",
            "fallback_reason": None,
            "meta": {
                "operation": "web_crawl",
                "attempts": 1,
                "retries": 0,
                "duration_ms": 12,
                "timings": {"total_ms": 12},
            },
        },
    )

    assert record == {
        "action_type": "open_page",
        "url": "https://example.com/article",
        "final_url": "https://example.com/final",
        "status_code": 200,
        "content_type": "text/html",
        "objective": "Find the summary",
        "fallback_reason": None,
        "text_preview": "A concise extracted summary of the page body.",
    }


def test_build_web_crawl_action_record_summarizes_error_payload() -> None:
    record = build_web_crawl_action_record(
        url="https://example.com/article",
        payload={
            "error": {
                "kind": "http_error",
                "message": "upstream unavailable",
                "retryable": True,
                "status_code": 503,
                "attempt_number": 3,
                "operation": "web_crawl",
                "timings": {"total_ms": 100},
            },
            "meta": {
                "operation": "web_crawl",
                "attempts": 3,
                "retries": 2,
                "duration_ms": 100,
                "timings": {"total_ms": 100},
            },
        },
    )

    assert record == {
        "action_type": "open_page",
        "url": "https://example.com/article",
        "error_kind": "http_error",
        "message": "upstream unavailable",
        "retryable": True,
        "attempts": 3,
        "status_code": 503,
    }


def test_build_web_crawl_action_record_accepts_pydantic_error_payload() -> None:
    record = build_web_crawl_action_record(
        url="https://example.com/article",
        payload=WebCrawlError(
            error=ToolError(
                kind="http_error",
                message="upstream unavailable",
                retryable=True,
                status_code=503,
                attempt_number=3,
                operation="web_crawl",
                timings=ToolTimings(total_ms=100),
            ),
            meta=ToolMeta(
                operation="web_crawl",
                attempts=3,
                retries=2,
                duration_ms=100,
                timings=ToolTimings(total_ms=100),
            ),
        ),
    )

    assert record == {
        "action_type": "open_page",
        "url": "https://example.com/article",
        "error_kind": "http_error",
        "message": "upstream unavailable",
        "retryable": True,
        "attempts": 3,
        "status_code": 503,
    }


def test_build_web_crawl_action_record_summarizes_batch_payload() -> None:
    record = build_web_crawl_action_record(
        url="https://example.com/a",
        payload={
            "requested_urls": ["https://example.com/a", "https://example.com/b"],
            "items": [
                {
                    "url": "https://example.com/a",
                    "status": "failed",
                    "result": None,
                    "error": {
                        "kind": "http_error",
                        "message": "blocked",
                        "retryable": False,
                        "status_code": 403,
                        "attempt_number": None,
                        "operation": "web_crawl",
                        "timings": {"total_ms": 5},
                    },
                },
                {
                    "url": "https://example.com/b",
                    "status": "failed",
                    "result": None,
                    "error": {
                        "kind": "http_error",
                        "message": "unavailable",
                        "retryable": False,
                        "status_code": 503,
                        "attempt_number": None,
                        "operation": "web_crawl",
                        "timings": {"total_ms": 7},
                    },
                },
            ],
            "meta": {
                "operation": "web_crawl",
                "attempts": 2,
                "retries": 0,
                "duration_ms": 12,
                "timings": {"total_ms": 12},
            },
            "summary": {"attempted": 2, "succeeded": 0, "failed": 2},
        },
    )

    assert record == {
        "action_type": "open_page_batch",
        "url": "https://example.com/a",
        "requested_urls": ["https://example.com/a", "https://example.com/b"],
        "attempted": 2,
        "succeeded": 0,
        "failed": 2,
    }


def test_build_web_crawl_tool_truncates_extracted_content_for_agentic_budget() -> None:
    worker = HttpFetchWorker(http_client=_mock_http_client(_rich_article_handler))
    tool_instance = build_web_crawl_tool(
        max_content_chars=40,
        fetch_worker=worker,
    )

    payload = tool_instance.invoke(
        {
            "url": "https://example.com/article",
            "objective": "Find the focused passage",
        }
    )
    result = WebCrawlSuccess.model_validate(payload)

    assert tool_instance.name == "open_url"
    assert 0 < len(result.text) <= 40
    assert 0 < len(result.markdown) <= 40
    assert result.objective == "Find the focused passage"
    assert result.excerpts


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


def test_bounded_web_crawl_rejects_urls_outside_retrieval_policy_scope() -> None:
    tool_instance = build_web_crawl_tool(
        retrieval_policy=AgentRunRetrievalPolicy.model_validate(
            {
                "search": {
                    "include_domains": ["example.com"],
                    "exclude_domains": ["blocked.com"],
                }
            }
        )
    )

    payload = tool_instance.invoke({"url": "https://blocked.com/article"})
    result = WebCrawlError.model_validate(payload)

    assert result.error.kind == "invalid_request"
    assert result.error.message == "url is outside the configured retrieval policy domain scope"


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


def _batch_mixed_handler(request: httpx.Request) -> httpx.Response:
    if str(request.url) == "https://example.com/a":
        return _rich_article_handler(request)
    if str(request.url) == "https://example.com/b":
        return _retryable_failure_handler(request)
    raise AssertionError(f"unexpected request url: {request.url}")


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
