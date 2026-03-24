from __future__ import annotations

from time import perf_counter
from typing import Any

from langchain_core.tools import tool
from pydantic import ValidationError

from backend.app.crawler.fetch_orchestrator import run_fetch_orchestrator
from backend.app.crawler.http_worker import HttpFetchWorker
from backend.app.crawler.session_profiles import SessionProfileProvider
from backend.app.tools.schemas.open_url import (
    OpenUrlError,
    OpenUrlInput,
    OpenUrlSuccess,
    OpenUrlToolResult,
)
from backend.app.tools.schemas.open_url_batch import OpenUrlBatchSuccess
from backend.app.tools.open_url_batch import run_open_url_batch
from backend.app.tools._tool_utils import (
    build_tool_action_error_record,
    build_tool_error_payload,
    validation_error_message,
)


def create_http_fetch_worker() -> HttpFetchWorker:
    """Build the default HTTP fetch worker.

    Example input: `create_http_fetch_worker()`
    Example output: `HttpFetchWorker(...)`
    """
    return HttpFetchWorker()


def build_open_url_tool(
    *,
    max_content_chars: int = 6000,
    fetch_worker: HttpFetchWorker | None = None,
    session_profile_provider: SessionProfileProvider | None = None,
    browser_fetcher=None,
):
    """Build the bounded LangChain crawl tool.

    Example input: `build_open_url_tool(max_content_chars=4000)`
    Example output: `StructuredTool(name="open_url", ...)`
    """
    bounded_limit = max(0, max_content_chars)

    @tool("open_url", args_schema=OpenUrlInput)
    def bounded_open_url(
        url: str | None = None,
        urls: list[str] | None = None,
    ) -> OpenUrlToolResult:
        """Fetch one page or a bounded batch of pages and return typed crawl output.

        Input:
        - Exactly one of `url` or `urls` must be provided.
        - `url`: One absolute `http` or `https` page URL to fetch.
        - `urls`: One to five absolute `http` or `https` page URLs to fetch in deterministic input order.

        Output:
        - `OpenUrlSuccess` for single-page success.
        - `OpenUrlBatchSuccess` for batch requests, with ordered per-item `succeeded` or `failed` entries.
        - `OpenUrlError` for invalid single requests or single-page failures.
        """
        payload = run_open_url(
            url=url,
            urls=urls,
            fetch_worker=fetch_worker,
            session_profile_provider=session_profile_provider,
            browser_fetcher=browser_fetcher,
        )
        return _truncate_open_url_payload(payload, max_content_chars=bounded_limit)

    return bounded_open_url


def run_open_url(
    *,
    url: str | None = None,
    urls: list[str] | None = None,
    fetch_worker: HttpFetchWorker | None = None,
    session_profile_provider: SessionProfileProvider | None = None,
    browser_fetcher=None,
) -> OpenUrlToolResult:
    """Run the crawl pipeline without LangChain wrapping.

    Example input: `run_open_url(url="https://example.com/article")`
    Example output: `OpenUrlSuccess(final_url="https://example.com/article", ...)`
    """
    operation_start = perf_counter()
    try:
        validated_input = OpenUrlInput(url=url, urls=urls)
        if validated_input.urls is not None:
            worker = fetch_worker or create_http_fetch_worker()

            def crawl_batch_item(item_url: str) -> OpenUrlToolResult:
                return run_open_url(
                    url=item_url,
                    fetch_worker=worker,
                    session_profile_provider=session_profile_provider,
                    browser_fetcher=browser_fetcher,
                )

            return run_open_url_batch(
                urls=[str(item) for item in validated_input.urls],
                crawl_one=crawl_batch_item,
            )

        return run_fetch_orchestrator(
            url=str(validated_input.url),
            fetch_worker=fetch_worker or create_http_fetch_worker(),
            session_profile_provider=session_profile_provider,
            browser_fetcher=browser_fetcher,
        )
    except ValidationError as exc:
        return _build_open_url_error_payload(
            operation_start=operation_start,
            kind="invalid_request",
            message=validation_error_message(exc),
            retryable=False,
        )
    except Exception:
        return _build_open_url_error_payload(
            operation_start=operation_start,
            kind="internal_error",
            message="unexpected open_url failure",
            retryable=False,
        )


open_url = build_open_url_tool()


def _elapsed_ms(start: float) -> int:
    """Convert a perf counter start value into elapsed milliseconds.

    Example input: `_elapsed_ms(123.0)`
    Example output: `17`
    """
    return int((perf_counter() - start) * 1000)


def _build_open_url_error_payload(
    *,
    operation_start: float,
    kind: str,
    message: str,
    retryable: bool,
    operation: str = "open_url",
) -> OpenUrlError:
    """Build a typed crawl error envelope.

    Example input: `_build_open_url_error_payload(operation_start=t0, kind="invalid_request", message="bad url", retryable=False)`
    Example output: `OpenUrlError(error=ToolError(kind="invalid_request", ...), ...)`
    """
    envelope = build_tool_error_payload(
        kind=kind,
        message=message,
        retryable=retryable,
        total_ms=_elapsed_ms(operation_start),
        operation=operation,
    )
    return OpenUrlError(error=envelope.error, meta=envelope.meta)


def _truncate_open_url_payload(payload: OpenUrlToolResult, *, max_content_chars: int) -> OpenUrlToolResult:
    """Trim crawl text fields while preserving typed success/error output.

    Example input: `_truncate_open_url_payload(OpenUrlSuccess(text="A"*100, ...), max_content_chars=40)`
    Example output: `OpenUrlSuccess(text="AAAA...", markdown="AAAA...", ...)`
    """
    try:
        success = OpenUrlSuccess.model_validate(payload)
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


def build_open_url_action_record(
    *,
    url: str,
    payload: Any,
    preview_chars: int = 160,
) -> dict[str, Any]:
    """Summarize crawl output for runtime action traces.

    Example input: `build_open_url_action_record(url="https://example.com", payload=OpenUrlSuccess(...))`
    Example output: `{"action_type": "open_page", "url": "https://example.com", ...}`
    """
    normalized_url = url.strip()

    try:
        batch = OpenUrlBatchSuccess.model_validate(payload)
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
        success = OpenUrlSuccess.model_validate(payload)
        text_preview = success.text[: max(preview_chars, 0)].strip()
        return {
            "action_type": "open_page",
            "url": str(success.url),
            "final_url": str(success.final_url),
            "status_code": success.status_code,
            "content_type": success.content_type,
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
