from __future__ import annotations

from time import perf_counter
from typing import Any, Callable

from langchain_core.tools import tool
from pydantic import ValidationError

from backend.agent.types import AgentRunRetrievalPolicy
from backend.app.contracts.web_crawl import WebCrawlError, WebCrawlInput, WebCrawlSuccess
from backend.app.crawler.extractor import extract_content, extraction_result_from_fetch_failure
from backend.app.crawler.http_worker import HttpFetchFailure, HttpFetchWorker
from backend.app.tools._tool_utils import (
    build_tool_action_error_record,
    build_tool_error_payload,
    domain_scope_kwargs,
    is_url_allowed,
    validation_error_message,
)


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
    def bounded_web_crawl(url: str, objective: str | None = None) -> dict[str, Any]:
        """Fetch a URL, extract main content, and return a structured result or error envelope."""
        effective_policy = retrieval_policy or AgentRunRetrievalPolicy()
        if not is_url_allowed(url, **domain_scope_kwargs(effective_policy.search)):
            return build_tool_error_payload(
                kind="invalid_request",
                message="url is outside the configured retrieval policy domain scope",
                retryable=False,
                total_ms=0,
                operation="web_crawl",
            )
        payload = runner(url=url, objective=objective)
        return _truncate_crawl_payload(payload, max_content_chars=bounded_limit)

    return bounded_web_crawl


def run_web_crawl(
    *,
    url: str,
    objective: str | None = None,
    fetch_worker: HttpFetchWorker | None = None,
) -> dict[str, Any]:
    operation_start = perf_counter()
    try:
        validated_input = WebCrawlInput(url=url, objective=objective)
        fetch_result = (fetch_worker or create_http_fetch_worker()).fetch(
            url=str(validated_input.url)
        )

        if isinstance(fetch_result, HttpFetchFailure):
            if fetch_result.error.kind == "unsupported_content_type":
                return _build_fetch_failure_success(
                    validated_input=validated_input,
                    fetch_result=fetch_result,
                )

            return WebCrawlError(
                error=fetch_result.error,
                meta=fetch_result.meta,
            ).model_dump(mode="json")

        extraction_result = extract_content(
            body=fetch_result.body,
            content_type=fetch_result.content_type,
            objective=validated_input.objective,
        )
        return _build_crawl_success_payload(
            validated_input=validated_input,
            final_url=fetch_result.final_url,
            extraction_text=extraction_result.text,
            extraction_markdown=extraction_result.markdown,
            excerpts=extraction_result.excerpts,
            status_code=fetch_result.status_code,
            content_type=fetch_result.content_type,
            fallback_reason=extraction_result.fallback_reason,
            meta=fetch_result.meta,
        )
    except ValidationError as exc:
        return _build_crawl_error_payload(
            operation_start=operation_start,
            kind="invalid_request",
            message=validation_error_message(exc),
            retryable=False,
        )
    except Exception:
        return _build_crawl_error_payload(
            operation_start=operation_start,
            kind="internal_error",
            message="unexpected web_crawl failure",
            retryable=False,
        )


web_crawl = build_web_crawl_tool()


def _elapsed_ms(start: float) -> int:
    return int((perf_counter() - start) * 1000)


def _build_crawl_error_payload(
    *,
    operation_start: float,
    kind: str,
    message: str,
    retryable: bool,
    operation: str = "web_crawl",
) -> dict[str, Any]:
    return build_tool_error_payload(
        kind=kind,
        message=message,
        retryable=retryable,
        total_ms=_elapsed_ms(operation_start),
        operation=operation,
    )


def _build_fetch_failure_success(
    *,
    validated_input: WebCrawlInput,
    fetch_result: HttpFetchFailure,
) -> dict[str, Any]:
    extraction_result = extraction_result_from_fetch_failure(fetch_result)
    return _build_crawl_success_payload(
        validated_input=validated_input,
        final_url=fetch_result.final_url or validated_input.url,
        extraction_text=extraction_result.text,
        extraction_markdown=extraction_result.markdown,
        excerpts=extraction_result.excerpts,
        status_code=fetch_result.status_code or 200,
        content_type=fetch_result.content_type or "application/octet-stream",
        fallback_reason=extraction_result.fallback_reason,
        meta=fetch_result.meta,
    )


def _build_crawl_success_payload(
    *,
    validated_input: WebCrawlInput,
    final_url: Any,
    extraction_text: str,
    extraction_markdown: str,
    excerpts: Any,
    status_code: int,
    content_type: str,
    fallback_reason: str | None,
    meta: Any,
) -> dict[str, Any]:
    return WebCrawlSuccess(
        url=validated_input.url,
        final_url=final_url,
        text=extraction_text,
        markdown=extraction_markdown,
        objective=validated_input.objective,
        excerpts=excerpts,
        status_code=status_code,
        content_type=content_type,
        fallback_reason=fallback_reason,
        meta=meta,
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


def build_web_crawl_action_record(
    *,
    url: str,
    payload: dict[str, Any],
    preview_chars: int = 160,
) -> dict[str, Any]:
    normalized_url = url.strip()

    try:
        success = WebCrawlSuccess.model_validate(payload)
        text_preview = success.text[: max(preview_chars, 0)].strip()
        return {
            "action_type": "open_page",
            "url": str(success.url),
            "final_url": str(success.final_url),
            "status_code": success.status_code,
            "content_type": success.content_type,
            "objective": success.objective,
            "fallback_reason": success.fallback_reason,
            "text_preview": text_preview,
        }
    except ValidationError:
        pass

    action_record = build_tool_action_error_record(
        action_type="open_page",
        subject_key="url",
        subject_value=normalized_url,
        payload=payload,
    )
    if action_record is not None:
        return action_record

    return {
        "action_type": "open_page",
        "url": normalized_url,
    }
