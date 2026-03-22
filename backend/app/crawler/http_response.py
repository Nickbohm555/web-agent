from __future__ import annotations

import httpx

from backend.app.crawler.content_types import is_supported_content_type
from backend.app.crawler.http_errors import (
    NonRetryableHttpFetchError,
    RetryableHttpFetchError,
)


def raise_for_status(response: httpx.Response, *, attempt_number: int) -> None:
    status_code = response.status_code
    if status_code == 429 or status_code >= 500:
        raise RetryableHttpFetchError(
            kind="http_error",
            message="origin returned a retryable HTTP status",
            status_code=status_code,
            attempt_number=attempt_number,
            final_url=str(response.url),
            content_type=normalized_content_type(response),
        )
    if 400 <= status_code < 500:
        raise NonRetryableHttpFetchError(
            kind="http_error",
            message="origin returned a terminal HTTP status",
            status_code=status_code,
            attempt_number=attempt_number,
            final_url=str(response.url),
            content_type=normalized_content_type(response),
        )


def validate_content_type(response: httpx.Response, *, attempt_number: int) -> None:
    content_type = normalized_content_type(response)
    if not is_supported_content_type(content_type):
        raise NonRetryableHttpFetchError(
            kind="unsupported_content_type",
            message="origin returned an unsupported content type",
            status_code=response.status_code,
            attempt_number=attempt_number,
            final_url=str(response.url),
            content_type=content_type or None,
        )


def read_body(response: httpx.Response, *, max_response_bytes: int) -> str:
    declared_length = response.headers.get("content-length")
    if declared_length is not None:
        try:
            if int(declared_length) > max_response_bytes:
                raise_response_too_large(response)
        except ValueError:
            pass

    body = response.text
    if len(body.encode(response.encoding or "utf-8", errors="ignore")) > max_response_bytes:
        raise_response_too_large(response)
    return body


def normalized_content_type(response: httpx.Response) -> str:
    return response.headers.get("content-type", "").split(";", 1)[0].strip().lower()


def raise_response_too_large(response: httpx.Response) -> None:
    raise NonRetryableHttpFetchError(
        kind="response_too_large",
        message="response exceeded the maximum allowed size",
        status_code=response.status_code,
        attempt_number=1,
        final_url=str(response.url),
        content_type=normalized_content_type(response) or None,
    )
