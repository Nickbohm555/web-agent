from __future__ import annotations

from backend.app.crawler.content_types import is_supported_content_type
from backend.app.crawler.schemas import HttpFetchFailure
from backend.app.crawler.excerpt_selection import segment_passages
from backend.app.tools.schemas.open_url import ExtractionResult

import trafilatura

MIN_EXTRACTED_TEXT_CHARS = 120


def extract_content(
    *,
    body: str,
    content_type: str | None,
) -> ExtractionResult:
    normalized_content_type = (content_type or "").strip().lower()
    if not is_supported_content_type(normalized_content_type):
        return _build_empty_extraction_result(
            state="unsupported-content-type",
            fallback_reason="unsupported-content-type",
        )

    markdown = _extract_output(body=body, output_format="markdown")
    text = _extract_output(body=body, output_format="txt")
    full_markdown = markdown or text
    if len(text) < MIN_EXTRACTED_TEXT_CHARS:
        return ExtractionResult(
            state="low-content-quality",
            text=text,
            markdown=full_markdown,
            excerpts=[],
            fallback_reason="low-content-quality",
        )

    excerpts = segment_passages(markdown=full_markdown, text=text)[:1]
    return ExtractionResult(
        state="ok",
        text=text,
        markdown=full_markdown,
        excerpts=excerpts,
        fallback_reason=None,
    )


def extraction_result_from_fetch_failure(failure: HttpFetchFailure) -> ExtractionResult:
    fallback_reason = (
        "unsupported-content-type"
        if failure.error.kind == "unsupported_content_type"
        else "network-error"
    )
    return _build_empty_extraction_result(
        state=fallback_reason,
        fallback_reason=fallback_reason,
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


def _build_empty_extraction_result(
    *,
    state: str,
    fallback_reason: str,
) -> ExtractionResult:
    return ExtractionResult(
        state=state,
        text="",
        markdown="",
        excerpts=[],
        fallback_reason=fallback_reason,
    )
