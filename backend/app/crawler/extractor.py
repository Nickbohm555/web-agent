from __future__ import annotations

from backend.app.contracts.web_crawl import ExtractionResult
from backend.app.crawler.http_worker import HttpFetchFailure, SUPPORTED_CONTENT_TYPES

import trafilatura

MIN_EXTRACTED_TEXT_CHARS = 120


def extract_content(*, body: str, content_type: str | None) -> ExtractionResult:
    normalized_content_type = (content_type or "").strip().lower()
    if not _is_supported_content_type(normalized_content_type):
        return ExtractionResult(
            state="unsupported-content-type",
            text="",
            markdown="",
            fallback_reason="unsupported-content-type",
        )

    markdown = _extract_output(body=body, output_format="markdown")
    text = _extract_output(body=body, output_format="txt")
    if len(text) < MIN_EXTRACTED_TEXT_CHARS:
        return ExtractionResult(
            state="low-content-quality",
            text=text,
            markdown=markdown,
            fallback_reason="low-content-quality",
        )

    return ExtractionResult(
        state="ok",
        text=text,
        markdown=markdown or text,
        fallback_reason=None,
    )


def extraction_result_from_fetch_failure(failure: HttpFetchFailure) -> ExtractionResult:
    if failure.error.kind == "unsupported_content_type":
        return ExtractionResult(
            state="unsupported-content-type",
            text="",
            markdown="",
            fallback_reason="unsupported-content-type",
        )

    return ExtractionResult(
        state="network-error",
        text="",
        markdown="",
        fallback_reason="network-error",
    )


def _extract_output(*, body: str, output_format: str) -> str:
    extracted = trafilatura.extract(
        body,
        output_format=output_format,
        include_comments=False,
        include_tables=False,
        favor_precision=True,
        fast=True,
    )
    return (extracted or "").strip()


def _is_supported_content_type(content_type: str) -> bool:
    return any(content_type.startswith(value) for value in SUPPORTED_CONTENT_TYPES)
