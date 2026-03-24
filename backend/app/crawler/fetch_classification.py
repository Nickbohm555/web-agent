from __future__ import annotations

from typing import Optional, Union

from backend.app.crawler.http_worker import HttpFetchFailure, HttpFetchSuccess
from backend.app.crawler.schemas.fetch_strategy import FetchClassification
from backend.app.tools.schemas.open_url import ExtractionResult


def classify_http_fetch(
    fetch_result: Union[HttpFetchSuccess, HttpFetchFailure],
    *,
    extraction_result: Optional[ExtractionResult] = None,
) -> FetchClassification:
    if isinstance(fetch_result, HttpFetchFailure):
        return classify_http_failure(fetch_result)

    if extraction_result is not None and extraction_result.state == "low-content-quality":
        return FetchClassification(kind="low_content_quality", block_reason="low_content_quality")

    return FetchClassification(kind="ok")


def classify_http_failure(fetch_result: HttpFetchFailure) -> FetchClassification:
    status_code = fetch_result.error.status_code or fetch_result.status_code

    if fetch_result.error.kind == "unsupported_content_type":
        return FetchClassification(kind="unsupported_content_type")
    if fetch_result.error.kind == "network_error":
        return FetchClassification(kind="network_error")
    if status_code == 401:
        return FetchClassification(kind="auth_required", block_reason="http_401")
    if status_code == 403:
        return FetchClassification(kind="blocked", block_reason="http_403")

    return FetchClassification(kind="network_error", block_reason=fetch_result.error.kind)
