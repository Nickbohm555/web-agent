from __future__ import annotations


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
