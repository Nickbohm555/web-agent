from __future__ import annotations

from time import perf_counter
from typing import Any, Callable
from urllib.parse import urlparse

from langchain_core.tools import tool
from pydantic import ValidationError

from backend.agent.types import AgentRunRetrievalPolicy
from backend.app.contracts.web_crawl import WebCrawlError, WebCrawlInput, WebCrawlSuccess
from backend.app.crawler.extractor import extract_content, extraction_result_from_fetch_failure
from backend.app.crawler.http_worker import HttpFetchFailure, HttpFetchWorker
from backend.app.tools._tool_utils import build_tool_error_payload, validation_error_message


def create_http_fetch_worker() -> HttpFetchWorker:
    return HttpFetchWorker()


def build_web_crawl_tool(
    *,
    max_content_chars: int = 6000,
    retrieval_policy: AgentRunRetrievalPolicy | None = None,
    crawl_runner: Callable[..., dict[str, Any]] | None = None,
):
    bounded_limit = max(0, max_content_chars)
    runner = crawl_runner or run_web_crawl

    @tool("web_crawl", args_schema=WebCrawlInput)
    def bounded_web_crawl(url: str) -> dict[str, Any]:
        """Fetch a URL, extract main content, and return a structured result or error envelope."""
        effective_policy = retrieval_policy or AgentRunRetrievalPolicy()
        if not _is_url_allowed(url, effective_policy):
            return build_tool_error_payload(
                kind="invalid_request",
                message="url is outside the configured retrieval policy domain scope",
                retryable=False,
                total_ms=0,
                operation="web_crawl",
            )
        payload = runner(url=url)
        return _truncate_crawl_payload(payload, max_content_chars=bounded_limit)

    return bounded_web_crawl


def run_web_crawl(*, url: str, fetch_worker: HttpFetchWorker | None = None) -> dict[str, Any]:
    operation_start = perf_counter()
    try:
        validated_input = WebCrawlInput(url=url)
        fetch_result = (fetch_worker or create_http_fetch_worker()).fetch(url=str(validated_input.url))

        if isinstance(fetch_result, HttpFetchFailure):
            if fetch_result.error.kind == "unsupported_content_type":
                return _build_fetch_failure_success(
                    validated_url=validated_input.url,
                    fetch_result=fetch_result,
                )

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
        return build_tool_error_payload(
            kind="invalid_request",
            message=validation_error_message(exc),
            retryable=False,
            total_ms=total_ms,
            operation="web_crawl",
        )
    except Exception:
        total_ms = _elapsed_ms(operation_start)
        return build_tool_error_payload(
            kind="internal_error",
            message="unexpected web_crawl failure",
            retryable=False,
            total_ms=total_ms,
            operation="web_crawl",
        )


web_crawl = build_web_crawl_tool()


def _elapsed_ms(start: float) -> int:
    return int((perf_counter() - start) * 1000)


def _build_fetch_failure_success(
    *,
    validated_url: Any,
    fetch_result: HttpFetchFailure,
) -> dict[str, Any]:
    extraction_result = extraction_result_from_fetch_failure(fetch_result)
    return WebCrawlSuccess(
        url=validated_url,
        final_url=fetch_result.final_url or validated_url,
        text=extraction_result.text,
        markdown=extraction_result.markdown,
        status_code=fetch_result.status_code or 200,
        content_type=fetch_result.content_type or "application/octet-stream",
        fallback_reason=extraction_result.fallback_reason,
        meta=fetch_result.meta,
    ).model_dump(mode="json")


def _truncate_crawl_payload(payload: dict[str, Any], *, max_content_chars: int) -> dict[str, Any]:
    try:
        success = WebCrawlSuccess.model_validate(payload)
    except ValidationError:
        return payload

    if max_content_chars <= 0:
        truncated_text = ""
        truncated_markdown = ""
    else:
        truncated_text = success.text[:max_content_chars].strip()
        truncated_markdown = success.markdown[:max_content_chars].strip()

    return success.model_copy(
        update={
            "text": truncated_text,
            "markdown": truncated_markdown,
        }
    ).model_dump(mode="json")


def _is_url_allowed(url: str, retrieval_policy: AgentRunRetrievalPolicy) -> bool:
    include_domains = retrieval_policy.search.include_domains
    exclude_domains = retrieval_policy.search.exclude_domains
    if not include_domains and not exclude_domains:
        return True

    hostname = _normalize_hostname(url)
    if hostname is None:
        return False

    if any(_hostname_matches(hostname, blocked) for blocked in exclude_domains):
        return False

    if not include_domains:
        return True

    return any(_hostname_matches(hostname, allowed) for allowed in include_domains)


def _hostname_matches(hostname: str, domain: str) -> bool:
    return hostname == domain or hostname.endswith(f".{domain}")


def _normalize_hostname(value: str) -> str | None:
    normalized_value = str(value)
    parsed = urlparse(
        normalized_value if "://" in normalized_value else f"https://{normalized_value}"
    )
    hostname = parsed.hostname
    if hostname is None:
        return None
    return hostname.strip().lower()
