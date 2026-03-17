from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

import httpx

from backend.app.contracts.tool_errors import ToolError, ToolMeta, ToolTimings
from backend.app.core.retry import execute_with_retry

DEFAULT_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
DEFAULT_MAX_RESPONSE_BYTES = 1_000_000
SUPPORTED_CONTENT_TYPES = ("text/html", "application/xhtml+xml")


@dataclass(frozen=True)
class HttpFetchSuccess:
    url: str
    final_url: str
    status_code: int
    content_type: str
    body: str
    meta: ToolMeta


@dataclass(frozen=True)
class HttpFetchFailure:
    url: str
    final_url: str | None
    status_code: int | None
    content_type: str | None
    error: ToolError
    meta: ToolMeta


class HttpFetchError(Exception):
    def __init__(
        self,
        *,
        kind: str,
        message: str,
        retryable: bool,
        status_code: int | None = None,
        attempt_number: int | None = None,
        final_url: str | None = None,
        content_type: str | None = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.retryable = retryable
        self.status_code = status_code
        self.attempt_number = attempt_number
        self.final_url = final_url
        self.content_type = content_type


class RetryableHttpFetchError(HttpFetchError):
    def __init__(self, **kwargs: object) -> None:
        super().__init__(retryable=True, **kwargs)


class NonRetryableHttpFetchError(HttpFetchError):
    def __init__(self, **kwargs: object) -> None:
        super().__init__(retryable=False, **kwargs)


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

            self._raise_for_status(response, attempt_number=attempt_number)
            self._validate_content_type(response, attempt_number=attempt_number)
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
                content_type=_normalized_content_type(response),
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

    def _raise_for_status(self, response: httpx.Response, *, attempt_number: int) -> None:
        status_code = response.status_code
        if status_code == 429 or status_code >= 500:
            raise RetryableHttpFetchError(
                kind="http_error",
                message="origin returned a retryable HTTP status",
                status_code=status_code,
                attempt_number=attempt_number,
                final_url=str(response.url),
                content_type=_normalized_content_type(response),
            )
        if 400 <= status_code < 500:
            raise NonRetryableHttpFetchError(
                kind="http_error",
                message="origin returned a terminal HTTP status",
                status_code=status_code,
                attempt_number=attempt_number,
                final_url=str(response.url),
                content_type=_normalized_content_type(response),
            )

    def _validate_content_type(self, response: httpx.Response, *, attempt_number: int) -> None:
        content_type = _normalized_content_type(response)
        if not any(content_type.startswith(value) for value in SUPPORTED_CONTENT_TYPES):
            raise NonRetryableHttpFetchError(
                kind="unsupported_content_type",
                message="origin returned an unsupported content type",
                status_code=response.status_code,
                attempt_number=attempt_number,
                final_url=str(response.url),
                content_type=content_type or None,
            )

    def _read_body(self, response: httpx.Response) -> str:
        declared_length = response.headers.get("content-length")
        if declared_length is not None:
            try:
                if int(declared_length) > self._max_response_bytes:
                    raise NonRetryableHttpFetchError(
                        kind="response_too_large",
                        message="response exceeded the maximum allowed size",
                        status_code=response.status_code,
                        attempt_number=1,
                        final_url=str(response.url),
                        content_type=_normalized_content_type(response) or None,
                    )
            except ValueError:
                pass

        body = response.text
        if len(body.encode(response.encoding or "utf-8", errors="ignore")) > self._max_response_bytes:
            raise NonRetryableHttpFetchError(
                kind="response_too_large",
                message="response exceeded the maximum allowed size",
                status_code=response.status_code,
                attempt_number=1,
                final_url=str(response.url),
                content_type=_normalized_content_type(response) or None,
            )
        return body


def _normalized_content_type(response: httpx.Response) -> str:
    return response.headers.get("content-type", "").split(";", 1)[0].strip().lower()


def _elapsed_ms(start: float) -> int:
    return int((perf_counter() - start) * 1000)

