from __future__ import annotations

from time import perf_counter
from typing import Any

from langchain_core.tools import tool
from pydantic import ValidationError
from pydantic.networks import HttpUrl

from backend.agent.schemas import AgentRunRetrievalPolicy
from backend.app.crawler.fetch_orchestrator import run_fetch_orchestrator
from backend.app.crawler.http_worker import HttpFetchWorker
from backend.app.crawler.session_profiles import SessionProfileProvider
from backend.app.tools.schemas.web_crawl import (
    WebCrawlError,
    WebCrawlInput,
    WebCrawlSuccess,
    WebCrawlToolResult,
)
from backend.app.tools.schemas.web_crawl_batch import WebCrawlBatchSuccess
from backend.app.tools.web_crawl_batch import run_web_crawl_batch
from backend.app.tools._tool_utils import (
    build_tool_action_error_record,
    build_tool_error_payload,
    domain_scope_kwargs,
    is_url_allowed,
    validation_error_message,
)


def create_http_fetch_worker() -> HttpFetchWorker:
    """Build the default HTTP fetch worker.

    Example input: `create_http_fetch_worker()`
    Example output: `HttpFetchWorker(...)`
    """
    return HttpFetchWorker()


def build_web_crawl_tool(
    *,
    max_content_chars: int = 6000,
    retrieval_policy: AgentRunRetrievalPolicy | None = None,
    fetch_worker: HttpFetchWorker | None = None,
    session_profile_provider: SessionProfileProvider | None = None,
    browser_fetcher=None,
):
    """Build the bounded LangChain crawl tool.

    Example input: `build_web_crawl_tool(max_content_chars=4000)`
    Example output: `StructuredTool(name="web_crawl", ...)`
    """
    bounded_limit = max(0, max_content_chars)

    @tool("web_crawl", args_schema=WebCrawlInput)
    def bounded_web_crawl(
        url: str | None = None,
        urls: list[str] | None = None,
        objective: str | None = None,
    ) -> WebCrawlToolResult:
        """Fetch one allowed page or a bounded batch of allowed pages and return typed crawl output.

        Input:
        - Exactly one of `url` or `urls` must be provided.
        - `url`: One absolute `http` or `https` page URL to fetch.
        - `urls`: One to five absolute `http` or `https` page URLs to fetch in deterministic input order.
        - `objective`: Optional short instruction describing what the agent wants from the page, such as "Find the refund policy" or "Summarize pricing details". This helps the extractor prioritize relevant excerpts but does not change which URL is fetched.

        Output:
        - `WebCrawlSuccess` for single-page success.
        - `WebCrawlBatchSuccess` for batch requests, with ordered per-item `succeeded` or `failed` entries.
        - `WebCrawlError` for invalid single requests or single-page failures.
        """
        payload = run_web_crawl(
            url=url,
            urls=urls,
            objective=objective,
            fetch_worker=fetch_worker,
            retrieval_policy=retrieval_policy,
            session_profile_provider=session_profile_provider,
            browser_fetcher=browser_fetcher,
        )
        return _truncate_crawl_payload(payload, max_content_chars=bounded_limit)

    return bounded_web_crawl


def run_web_crawl(
    *,
    url: str | None = None,
    urls: list[str] | None = None,
    objective: str | None = None,
    fetch_worker: HttpFetchWorker | None = None,
    retrieval_policy: AgentRunRetrievalPolicy | None = None,
    session_profile_provider: SessionProfileProvider | None = None,
    browser_fetcher=None,
) -> WebCrawlToolResult:
    """Run the crawl pipeline without LangChain wrapping.

    Example input: `run_web_crawl(url="https://example.com/article", objective="Find pricing")`
    Example output: `WebCrawlSuccess(final_url="https://example.com/article", ...)`
    """
    operation_start = perf_counter()
    try:
        validated_input = WebCrawlInput(url=url, urls=urls, objective=objective)
        if validated_input.urls is not None:
            worker = fetch_worker or create_http_fetch_worker()
            return run_web_crawl_batch(
                urls=[str(item) for item in validated_input.urls],
                objective=validated_input.objective,
                retrieval_policy=retrieval_policy,
                crawl_one=lambda item_url, item_objective: run_web_crawl(
                    url=item_url,
                    objective=item_objective,
                    fetch_worker=worker,
                    retrieval_policy=retrieval_policy,
                    session_profile_provider=session_profile_provider,
                    browser_fetcher=browser_fetcher,
                ),
            )

        effective_policy = retrieval_policy or AgentRunRetrievalPolicy()
        if not is_url_allowed(str(validated_input.url), **domain_scope_kwargs(effective_policy.search)):
            envelope = build_tool_error_payload(
                kind="invalid_request",
                message="url is outside the configured retrieval policy domain scope",
                retryable=False,
                total_ms=0,
                operation="web_crawl",
            )
            return WebCrawlError(error=envelope.error, meta=envelope.meta)

        return run_fetch_orchestrator(
            url=str(validated_input.url),
            objective=validated_input.objective,
            fetch_worker=fetch_worker or create_http_fetch_worker(),
            session_profile_provider=session_profile_provider,
            browser_fetcher=browser_fetcher,
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
    """Convert a perf counter start value into elapsed milliseconds.

    Example input: `_elapsed_ms(123.0)`
    Example output: `17`
    """
    return int((perf_counter() - start) * 1000)


def _build_crawl_error_payload(
    *,
    operation_start: float,
    kind: str,
    message: str,
    retryable: bool,
    operation: str = "web_crawl",
) -> WebCrawlError:
    """Build a typed crawl error envelope.

    Example input: `_build_crawl_error_payload(operation_start=t0, kind="invalid_request", message="bad url", retryable=False)`
    Example output: `WebCrawlError(error=ToolError(kind="invalid_request", ...), ...)`
    """
    envelope = build_tool_error_payload(
        kind=kind,
        message=message,
        retryable=retryable,
        total_ms=_elapsed_ms(operation_start),
        operation=operation,
    )
    return WebCrawlError(error=envelope.error, meta=envelope.meta)

def _truncate_crawl_payload(payload: WebCrawlToolResult, *, max_content_chars: int) -> WebCrawlToolResult:
    """Trim crawl text fields while preserving typed success/error output.

    Example input: `_truncate_crawl_payload(WebCrawlSuccess(text="A"*100, ...), max_content_chars=40)`
    Example output: `WebCrawlSuccess(text="AAAA...", markdown="AAAA...", ...)`
    """
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
    )


def build_web_crawl_action_record(
    *,
    url: str,
    payload: Any,
    preview_chars: int = 160,
) -> dict[str, Any]:
    """Summarize crawl output for runtime action traces.

    Example input: `build_web_crawl_action_record(url="https://example.com", payload=WebCrawlSuccess(...))`
    Example output: `{"action_type": "open_page", "url": "https://example.com", ...}`
    """
    normalized_url = url.strip()

    try:
        batch = WebCrawlBatchSuccess.model_validate(payload)
        return {
            "action_type": "open_page_batch",
            "url": normalized_url,
            "requested_urls": [str(item) for item in batch.requested_urls],
            "attempted": batch.summary.attempted,
            "succeeded": batch.summary.succeeded,
            "failed": batch.summary.failed,
        }
    except ValidationError:
        pass

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
