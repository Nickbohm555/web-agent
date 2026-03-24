from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from time import perf_counter
from typing import Callable

from backend.app.tools.schemas.tool_errors import ToolError, ToolTimings
from backend.app.tools.schemas.open_url import OpenUrlError, OpenUrlMeta, OpenUrlSuccess, OpenUrlToolResult
from backend.app.tools.schemas.open_url_batch import (
    OpenUrlBatchItemResult,
    OpenUrlBatchSuccess,
    OpenUrlBatchSummary,
)

PER_URL_TIMEOUT_SECONDS = 15
MAX_BATCH_WORKERS = 5


def run_open_url_batch(
    *,
    urls: list[str],
    crawl_one: Callable[[str], OpenUrlToolResult],
) -> OpenUrlBatchSuccess:
    """Run deterministic parallel crawl fan-out and return ordered typed batch results.

    Example input: `run_open_url_batch(urls=["https://example.com/a"], crawl_one=my_crawl)`
    Example output: `OpenUrlBatchSuccess(requested_urls=["https://example.com/a"], items=[...], ...)`
    """
    operation_start = perf_counter()
    requested_urls = list(urls)

    with ThreadPoolExecutor(max_workers=min(len(requested_urls), MAX_BATCH_WORKERS)) as pool:
        futures: dict[Future[OpenUrlToolResult], str] = {}
        results_by_url: dict[str, OpenUrlBatchItemResult] = {}

        for url in requested_urls:
            futures[pool.submit(crawl_one, url)] = url

        results_by_url.update(_await_batch_futures(futures))

    ordered_items = [results_by_url[url] for url in requested_urls]
    succeeded = sum(1 for item in ordered_items if item.status == "succeeded")
    failed = len(ordered_items) - succeeded
    total_ms = _elapsed_ms(operation_start)
    return OpenUrlBatchSuccess(
        requested_urls=requested_urls,
        items=ordered_items,
        meta=OpenUrlMeta(
            operation="open_url",
            attempts=max(len(requested_urls), 1),
            retries=0,
            duration_ms=total_ms,
            timings=ToolTimings(total_ms=total_ms),
            strategy_used="http",
            escalation_count=0,
            rendered=False,
            challenge_detected=False,
        ),
        summary=OpenUrlBatchSummary(
            attempted=len(requested_urls),
            succeeded=succeeded,
            failed=failed,
        ),
    )


def _await_batch_futures(
    futures: dict[Future[OpenUrlToolResult], str],
) -> dict[str, OpenUrlBatchItemResult]:
    results_by_url: dict[str, OpenUrlBatchItemResult] = {}
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


def _build_batch_item(*, url: str, payload: OpenUrlToolResult) -> OpenUrlBatchItemResult:
    success = _try_validate_success(payload)
    if success is not None:
        return OpenUrlBatchItemResult(
            url=url,
            status="succeeded",
            result=success,
            error=None,
        )

    error = OpenUrlError.model_validate(payload)
    return OpenUrlBatchItemResult(
        url=url,
        status="failed",
        result=None,
        error=error.error,
    )


def _build_timeout_item(url: str) -> OpenUrlBatchItemResult:
    return OpenUrlBatchItemResult(
        url=url,
        status="failed",
        result=None,
        error=ToolError(
            kind="timeout",
            message="open_url timed out",
            retryable=False,
            operation="open_url",
            timings=ToolTimings(total_ms=PER_URL_TIMEOUT_SECONDS * 1000),
        ),
    )


def _build_exception_item(url: str, exc: Exception) -> OpenUrlBatchItemResult:
    return OpenUrlBatchItemResult(
        url=url,
        status="failed",
        result=None,
        error=ToolError(
            kind="internal_error",
            message=str(exc) or "unexpected open_url failure",
            retryable=False,
            operation="open_url",
            timings=ToolTimings(total_ms=0),
        ),
    )


def _try_validate_success(payload: OpenUrlToolResult) -> OpenUrlSuccess | None:
    try:
        return OpenUrlSuccess.model_validate(payload)
    except Exception:
        return None


def _elapsed_ms(start: float) -> int:
    return int((perf_counter() - start) * 1000)
