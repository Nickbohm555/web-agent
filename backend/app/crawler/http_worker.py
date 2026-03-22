from __future__ import annotations

from time import perf_counter

import httpx

from backend.app.core.retry import execute_with_retry
from backend.app.crawler.content_types import SUPPORTED_CONTENT_TYPES
from backend.app.crawler.http_errors import HttpFetchError, RetryableHttpFetchError
from backend.app.crawler.http_response import (
    normalized_content_type,
    raise_for_status,
    read_body,
    validate_content_type,
)
from backend.app.crawler.schemas import HttpFetchFailure, HttpFetchSuccess
from backend.app.tools.schemas.tool_errors import ToolError, ToolMeta, ToolTimings

DEFAULT_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
DEFAULT_MAX_RESPONSE_BYTES = 1_000_000


class HttpFetchWorker:
    def __init__(
        self,
        *,
        timeout: httpx.Timeout = DEFAULT_TIMEOUT,
        max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._timeout = timeout
        self._max_response_bytes = max_response_bytes
        self._http_client = http_client

    def fetch(self, *, url: str) -> HttpFetchSuccess | HttpFetchFailure:
        operation_start = perf_counter()

        def perform_request(attempt_number: int) -> httpx.Response:
            try:
                response = self._get(url)
            except httpx.RequestError as exc:
                raise RetryableHttpFetchError(
                    kind="network_error",
                    message="request failed before a response was received",
                    attempt_number=attempt_number,
                ) from exc

            raise_for_status(response, attempt_number=attempt_number)
            validate_content_type(response, attempt_number=attempt_number)
            return response

        try:
            retry_result = execute_with_retry(
                perform_request,
                retryable_exceptions=(RetryableHttpFetchError,),
                max_attempts=3,
            )
            response = retry_result.value
            body = self._read_body(response)
            total_ms = _elapsed_ms(operation_start)
            return HttpFetchSuccess(
                url=url,
                final_url=str(response.url),
                status_code=response.status_code,
                content_type=normalized_content_type(response),
                body=body,
                meta=ToolMeta(
                    operation="web_crawl",
                    attempts=retry_result.attempts,
                    retries=retry_result.attempts - 1,
                    duration_ms=total_ms,
                    timings=ToolTimings(total_ms=total_ms),
                ),
            )
        except HttpFetchError as exc:
            total_ms = _elapsed_ms(operation_start)
            attempts = exc.attempt_number or 1
            timings = ToolTimings(total_ms=total_ms)
            return HttpFetchFailure(
                url=url,
                final_url=exc.final_url,
                status_code=exc.status_code,
                content_type=exc.content_type,
                error=ToolError(
                    kind=exc.kind,
                    message=exc.message,
                    retryable=exc.retryable,
                    status_code=exc.status_code,
                    attempt_number=attempts,
                    operation="web_crawl",
                    timings=timings,
                ),
                meta=ToolMeta(
                    operation="web_crawl",
                    attempts=attempts,
                    retries=max(attempts - 1, 0),
                    duration_ms=total_ms,
                    timings=timings,
                ),
            )

    def _get(self, url: str) -> httpx.Response:
        if self._http_client is not None:
            return self._http_client.get(url, timeout=self._timeout, follow_redirects=True)

        with httpx.Client(follow_redirects=True) as client:
            return client.get(url, timeout=self._timeout)

    def _read_body(self, response: httpx.Response) -> str:
        return read_body(response, max_response_bytes=self._max_response_bytes)


def _elapsed_ms(start: float) -> int:
    return int((perf_counter() - start) * 1000)
