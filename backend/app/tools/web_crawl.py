from __future__ import annotations

from time import perf_counter
from typing import Any

from langchain_core.tools import tool
from pydantic import ValidationError

from backend.app.contracts.tool_errors import ToolError, ToolErrorEnvelope, ToolMeta, ToolTimings
from backend.app.contracts.web_crawl import WebCrawlError, WebCrawlInput, WebCrawlSuccess
from backend.app.crawler.extractor import extract_content, extraction_result_from_fetch_failure
from backend.app.crawler.http_worker import HttpFetchFailure, HttpFetchWorker


def create_http_fetch_worker() -> HttpFetchWorker:
    return HttpFetchWorker()


def run_web_crawl(*, url: str, fetch_worker: HttpFetchWorker | None = None) -> dict[str, Any]:
    operation_start = perf_counter()
    try:
        validated_input = WebCrawlInput(url=url)
        fetch_result = (fetch_worker or create_http_fetch_worker()).fetch(url=str(validated_input.url))

        if isinstance(fetch_result, HttpFetchFailure):
            if fetch_result.error.kind == "unsupported_content_type":
                extraction_result = extraction_result_from_fetch_failure(fetch_result)
                return WebCrawlSuccess(
                    url=validated_input.url,
                    final_url=fetch_result.final_url or validated_input.url,
                    text=extraction_result.text,
                    markdown=extraction_result.markdown,
                    status_code=fetch_result.status_code or 200,
                    content_type=fetch_result.content_type or "application/octet-stream",
                    fallback_reason=extraction_result.fallback_reason,
                    meta=fetch_result.meta,
                ).model_dump(mode="json")

            return WebCrawlError(error=fetch_result.error, meta=fetch_result.meta).model_dump(mode="json")

        extraction_result = extract_content(
            body=fetch_result.body,
            content_type=fetch_result.content_type,
        )
        return WebCrawlSuccess(
            url=validated_input.url,
            final_url=fetch_result.final_url,
            text=extraction_result.text,
            markdown=extraction_result.markdown,
            status_code=fetch_result.status_code,
            content_type=fetch_result.content_type,
            fallback_reason=extraction_result.fallback_reason,
            meta=fetch_result.meta,
        ).model_dump(mode="json")
    except ValidationError as exc:
        total_ms = _elapsed_ms(operation_start)
        return ToolErrorEnvelope(
            error=ToolError(
                kind="invalid_request",
                message=_validation_error_message(exc),
                retryable=False,
                attempt_number=1,
                operation="web_crawl",
                timings=ToolTimings(total_ms=total_ms),
            ),
            meta=ToolMeta(
                operation="web_crawl",
                attempts=1,
                retries=0,
                duration_ms=total_ms,
                timings=ToolTimings(total_ms=total_ms),
            ),
        ).model_dump(mode="json")
    except Exception:
        total_ms = _elapsed_ms(operation_start)
        return ToolErrorEnvelope(
            error=ToolError(
                kind="internal_error",
                message="unexpected web_crawl failure",
                retryable=False,
                attempt_number=1,
                operation="web_crawl",
                timings=ToolTimings(total_ms=total_ms),
            ),
            meta=ToolMeta(
                operation="web_crawl",
                attempts=1,
                retries=0,
                duration_ms=total_ms,
                timings=ToolTimings(total_ms=total_ms),
            ),
        ).model_dump(mode="json")


@tool("web_crawl", args_schema=WebCrawlInput)
def web_crawl(url: str) -> dict[str, Any]:
    """Fetch a URL, extract main content, and return a structured result or error envelope."""
    return run_web_crawl(url=url)


def _elapsed_ms(start: float) -> int:
    return int((perf_counter() - start) * 1000)


def _validation_error_message(exc: ValidationError) -> str:
    first_error = exc.errors()[0]
    location = ".".join(str(part) for part in first_error.get("loc", []))
    if location:
        return f"{location}: {first_error['msg']}"
    return str(exc)
