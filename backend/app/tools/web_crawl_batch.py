from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from time import perf_counter
from typing import Callable

from backend.agent.schemas import AgentRunRetrievalPolicy
from backend.app.tools._tool_utils import build_tool_error_payload, domain_scope_kwargs, is_url_allowed
from backend.app.tools.schemas.tool_errors import ToolError, ToolTimings
from backend.app.tools.schemas.web_crawl import WebCrawlError, WebCrawlMeta, WebCrawlSuccess, WebCrawlToolResult
from backend.app.tools.schemas.web_crawl_batch import (
    WebCrawlBatchItemResult,
    WebCrawlBatchSuccess,
    WebCrawlBatchSummary,
)

PER_URL_TIMEOUT_SECONDS = 15
MAX_BATCH_WORKERS = 5


def run_web_crawl_batch(
    *,
    urls: list[str],
    objective: str | None,
    crawl_one: Callable[[str, str | None], WebCrawlToolResult],
    retrieval_policy: AgentRunRetrievalPolicy | None = None,
) -> WebCrawlBatchSuccess:
    """Run deterministic parallel crawl fan-out and return ordered typed batch results.

    Example input: `run_web_crawl_batch(urls=["https://example.com/a"], objective=None, crawl_one=my_crawl)`
    Example output: `WebCrawlBatchSuccess(requested_urls=["https://example.com/a"], items=[...], ...)`
    """
    operation_start = perf_counter()
    requested_urls = list(urls)
    policy = retrieval_policy or AgentRunRetrievalPolicy()

    with ThreadPoolExecutor(max_workers=min(len(requested_urls), MAX_BATCH_WORKERS)) as pool:
        futures: dict[Future[WebCrawlToolResult], str] = {}
        results_by_url: dict[str, WebCrawlBatchItemResult] = {}

        for url in requested_urls:
            if not is_url_allowed(url, **domain_scope_kwargs(policy.search)):
                results_by_url[url] = _build_invalid_request_item(url)
                continue
            futures[pool.submit(crawl_one, url, objective)] = url

        results_by_url.update(_await_batch_futures(futures))

    ordered_items = [results_by_url[url] for url in requested_urls]
    succeeded = sum(1 for item in ordered_items if item.status == "succeeded")
    failed = len(ordered_items) - succeeded
    total_ms = _elapsed_ms(operation_start)
    return WebCrawlBatchSuccess(
        requested_urls=requested_urls,
        items=ordered_items,
        meta=WebCrawlMeta(
            operation="web_crawl",
            attempts=max(len(requested_urls), 1),
            retries=0,
            duration_ms=total_ms,
            timings=ToolTimings(total_ms=total_ms),
            strategy_used="http",
            escalation_count=0,
            rendered=False,
            challenge_detected=False,
        ),
        summary=WebCrawlBatchSummary(
            attempted=len(requested_urls),
            succeeded=succeeded,
            failed=failed,
        ),
    )


def _await_batch_futures(
    futures: dict[Future[WebCrawlToolResult], str],
) -> dict[str, WebCrawlBatchItemResult]:
    results_by_url: dict[str, WebCrawlBatchItemResult] = {}
    pending = set(futures)

    while pending:
        done, pending = wait(
            pending,
            timeout=PER_URL_TIMEOUT_SECONDS,
            return_when=FIRST_COMPLETED,
        )
        if not done:
            for future in pending:
                future.cancel()
                url = futures[future]
                results_by_url[url] = _build_timeout_item(url)
            break

        for future in done:
            url = futures[future]
            try:
                payload = future.result()
            except Exception as exc:
                results_by_url[url] = _build_exception_item(url, exc)
                continue
            results_by_url[url] = _build_batch_item(url=url, payload=payload)

    return results_by_url


def _build_batch_item(*, url: str, payload: WebCrawlToolResult) -> WebCrawlBatchItemResult:
    success = _try_validate_success(payload)
    if success is not None:
        return WebCrawlBatchItemResult(
            url=url,
            status="succeeded",
            result=success,
            error=None,
        )

    error = WebCrawlError.model_validate(payload)
    return WebCrawlBatchItemResult(
        url=url,
        status="failed",
        result=None,
        error=error.error,
    )


def _build_invalid_request_item(url: str) -> WebCrawlBatchItemResult:
    envelope = build_tool_error_payload(
        kind="invalid_request",
        message="url is outside the configured retrieval policy domain scope",
        retryable=False,
        total_ms=0,
        operation="web_crawl",
    )
    return WebCrawlBatchItemResult(
        url=url,
        status="failed",
        result=None,
        error=envelope.error,
    )


def _build_timeout_item(url: str) -> WebCrawlBatchItemResult:
    return WebCrawlBatchItemResult(
        url=url,
        status="failed",
        result=None,
        error=ToolError(
            kind="timeout",
            message="web crawl timed out",
            retryable=False,
            operation="web_crawl",
            timings=ToolTimings(total_ms=PER_URL_TIMEOUT_SECONDS * 1000),
        ),
    )


def _build_exception_item(url: str, exc: Exception) -> WebCrawlBatchItemResult:
    return WebCrawlBatchItemResult(
        url=url,
        status="failed",
        result=None,
        error=ToolError(
            kind="internal_error",
            message=str(exc) or "unexpected web_crawl failure",
            retryable=False,
            operation="web_crawl",
            timings=ToolTimings(total_ms=0),
        ),
    )


def _try_validate_success(payload: WebCrawlToolResult) -> WebCrawlSuccess | None:
    try:
        return WebCrawlSuccess.model_validate(payload)
    except Exception:
        return None


def _elapsed_ms(start: float) -> int:
    return int((perf_counter() - start) * 1000)
