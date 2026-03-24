from __future__ import annotations

from time import perf_counter
from typing import Any, Callable, Mapping, Optional, Union

from backend.app.crawler.schemas.browser_fetch import (
    BrowserContextSeed,
    BrowserFetchFailure,
    BrowserFetchSuccess,
    StorageStateApplied,
)
from backend.app.tools.schemas.tool_errors import ToolError, ToolMeta, ToolTimings

BrowserFetchResult = Union[BrowserFetchSuccess, BrowserFetchFailure]
BrowserFetchImpl = Callable[[str, BrowserContextSeed], Union[BrowserFetchResult, Mapping[str, Any]]]


def browser_fetch(
    *,
    url: str,
    seed: BrowserContextSeed,
    fetch_impl: Optional[BrowserFetchImpl] = None,
) -> BrowserFetchResult:
    """Fetch a page through the browser seam and return typed browser content.

    Example input: `browser_fetch(url="https://example.com/dashboard", seed=BrowserContextSeed(), fetch_impl=my_impl)`
    Example output: `BrowserFetchSuccess(url="https://example.com/dashboard", final_url="https://example.com/dashboard", ...)`
    """
    if fetch_impl is None:
        return _build_unavailable_browser_failure(url=url, seed=seed)

    result = fetch_impl(url=url, seed=seed)
    if isinstance(result, (BrowserFetchSuccess, BrowserFetchFailure)):
        return result
    if "error" in result:
        return BrowserFetchFailure.model_validate(result)
    return BrowserFetchSuccess.model_validate(result)


def _build_unavailable_browser_failure(
    *,
    url: str,
    seed: BrowserContextSeed,
) -> BrowserFetchFailure:
    total_ms = _elapsed_ms(perf_counter())
    timings = ToolTimings(total_ms=total_ms)
    return BrowserFetchFailure(
        url=url,
        final_url=None,
        status_code=None,
        content_type=None,
        error=ToolError(
            kind="browser_navigation_failed",
            message="browser fetch implementation is not configured",
            retryable=False,
            operation="web_crawl",
            timings=timings,
        ),
        seed_applied=StorageStateApplied(
            cookies=bool(seed.cookies),
            headers=bool(seed.headers),
            local_storage=bool(seed.local_storage),
            session_storage=bool(seed.session_storage),
        ),
        meta=ToolMeta(
            operation="web_crawl",
            attempts=1,
            retries=0,
            duration_ms=total_ms,
            timings=timings,
        ),
    )


def _elapsed_ms(start: float) -> int:
    return int((perf_counter() - start) * 1000)
