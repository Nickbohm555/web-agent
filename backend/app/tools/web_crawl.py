from __future__ import annotations

from time import perf_counter
from typing import Any

from langchain_core.tools import tool
from pydantic import ValidationError
from pydantic.networks import HttpUrl

from backend.agent.schemas import AgentRunRetrievalPolicy
from backend.app.crawler.browser_worker import BrowserFetchWorker
from backend.app.crawler.fetch_orchestrator import CrawlSuccessEnvelope, FetchOrchestrator
from backend.app.crawler.http_worker import HttpFetchWorker
from backend.app.crawler.schemas.session_profile import SessionProfile
from backend.app.tools._tool_utils import (
    build_tool_action_error_record,
    build_tool_error_payload,
    domain_scope_kwargs,
    is_url_allowed,
    validation_error_message,
)
from backend.app.tools.schemas.tool_errors import ToolMeta
from backend.app.tools.schemas.web_crawl import (
    ExtractionResult,
    WebCrawlError,
    WebCrawlInput,
    WebCrawlSuccess,
    WebCrawlToolResult,
)
from backend.app.tools.tool_logging import log_web_crawl_result


def create_http_fetch_worker() -> HttpFetchWorker:
    """Build the default HTTP fetch worker.

    Example input: `create_http_fetch_worker()`
    Example output: `HttpFetchWorker(...)`
    """
    return HttpFetchWorker()


def create_browser_fetch_worker() -> BrowserFetchWorker:
    """Build the default browser fetch worker.

    Example input: `create_browser_fetch_worker()`
    Example output: `BrowserFetchWorker(...)`
    """
    return BrowserFetchWorker()


def create_fetch_orchestrator(
    *,
    fetch_worker: HttpFetchWorker | None = None,
    browser_fetch_worker: BrowserFetchWorker | None = None,
    session_profiles: list[SessionProfile] | None = None,
) -> FetchOrchestrator:
    """Build the session-aware crawl orchestrator.

    Example input: `create_fetch_orchestrator(fetch_worker=HttpFetchWorker())`
    Example output: `FetchOrchestrator(...)`
    """
    return FetchOrchestrator(
        http_fetch_worker=fetch_worker,
        browser_fetch_worker=browser_fetch_worker,
        session_profiles=session_profiles,
    )


def build_web_crawl_tool(
    *,
    max_content_chars: int = 6000,
    retrieval_policy: AgentRunRetrievalPolicy | None = None,
    fetch_worker: HttpFetchWorker | None = None,
    browser_fetch_worker: BrowserFetchWorker | None = None,
    session_profiles: list[SessionProfile] | None = None,
):
    """Build the bounded LangChain crawl tool.

    Example input: `build_web_crawl_tool(max_content_chars=4000)`
    Example output: `StructuredTool(name="web_crawl", ...)`
    """
    bounded_limit = max(0, max_content_chars)

    @tool("web_crawl", args_schema=WebCrawlInput)
    def bounded_web_crawl(url: str, objective: str | None = None) -> WebCrawlToolResult:
        """Fetch one allowed page through HTTP and browser retrieval paths, then return evidence-bearing content or a typed error.

        Input:
        - `url`: Absolute `http` or `https` page URL to fetch. The URL must be inside the current retrieval-policy domain scope or the tool returns an `invalid_request` error.
        - `objective`: Optional short instruction describing what the agent wants from the page, such as "Find the refund policy" or "Summarize pricing details". This helps excerpt selection after HTTP or browser retrieval.

        Output:
        - `WebCrawlSuccess` with normalized page text, markdown, excerpts, final URL, status code, strategy metadata, and content type when evidence is recovered.
        - `WebCrawlError` with a typed error envelope when validation, policy checks, HTTP/browser fetching, or extraction fails. Auth gates, challenge pages, unsupported content, and low-content pages are returned as typed failures instead of empty successes.
        """
        effective_policy = retrieval_policy or AgentRunRetrievalPolicy()
        if not is_url_allowed(url, **domain_scope_kwargs(effective_policy.search)):
            return _build_crawl_error_payload(
                total_ms=0,
                kind="invalid_request",
                message="url is outside the configured retrieval policy domain scope",
                retryable=False,
            )

        payload = run_web_crawl(
            url=url,
            objective=objective,
            fetch_worker=fetch_worker or create_http_fetch_worker(),
            browser_fetch_worker=browser_fetch_worker or create_browser_fetch_worker(),
            session_profiles=session_profiles,
        )
        bounded_payload = _truncate_crawl_payload(payload, max_content_chars=bounded_limit)
        log_web_crawl_result(url=url, objective=objective, payload=bounded_payload)
        return bounded_payload

    return bounded_web_crawl


def run_web_crawl(
    *,
    url: str,
    objective: str | None = None,
    fetch_worker: HttpFetchWorker | None = None,
    browser_fetch_worker: BrowserFetchWorker | None = None,
    session_profiles: list[SessionProfile] | None = None,
    fetch_orchestrator: FetchOrchestrator | None = None,
) -> WebCrawlToolResult:
    """Run the session-aware crawl pipeline without LangChain wrapping.

    Example input: `run_web_crawl(url="https://example.com/article", objective="Find pricing")`
    Example output: `WebCrawlSuccess(final_url="https://example.com/article", strategy_used="http", ...)`
    """
    operation_start = perf_counter()
    try:
        validated_input = WebCrawlInput(url=url, objective=objective)
        result = (fetch_orchestrator or create_fetch_orchestrator(
            fetch_worker=fetch_worker,
            browser_fetch_worker=browser_fetch_worker,
            session_profiles=session_profiles,
        )).crawl(
            url=str(validated_input.url),
            objective=validated_input.objective,
        )
        if isinstance(result, CrawlSuccessEnvelope):
            if not _has_recovered_evidence(result.extraction_result):
                return _build_crawl_error_payload(
                    total_ms=result.meta.duration_ms,
                    kind="low_content_quality",
                    message="page did not yield enough evidence after retrieval attempts",
                    retryable=False,
                    status_code=result.status_code,
                    attempt_number=result.meta.attempts,
                )
            return _build_crawl_success_payload(
                validated_input=validated_input,
                final_url=result.final_url,
                extraction_result=result.extraction_result,
                status_code=result.status_code,
                content_type=result.content_type,
                meta=result.meta,
                strategy_used=result.strategy_used,
                escalation_count=result.escalation_count,
                session_profile_id=result.session_profile_id,
                block_reason=result.block_reason,
                rendered=result.rendered,
                challenge_detected=result.challenge_detected,
            )
        return result
    except ValidationError as exc:
        return _build_crawl_error_payload(
            total_ms=_elapsed_ms(operation_start),
            kind="invalid_request",
            message=validation_error_message(exc),
            retryable=False,
        )
    except Exception:
        return _build_crawl_error_payload(
            total_ms=_elapsed_ms(operation_start),
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
    total_ms: int,
    kind: str,
    message: str,
    retryable: bool,
    status_code: int | None = None,
    attempt_number: int = 1,
    operation: str = "web_crawl",
) -> WebCrawlError:
    """Build a typed crawl error envelope.

    Example input: `_build_crawl_error_payload(total_ms=12, kind="invalid_request", message="bad url", retryable=False, status_code=400, attempt_number=1)`
    Example output: `WebCrawlError(error=ToolError(kind="invalid_request", ...), ...)`
    """
    envelope = build_tool_error_payload(
        kind=kind,
        message=message,
        retryable=retryable,
        total_ms=total_ms,
        operation=operation,
        status_code=status_code,
        attempt_number=attempt_number,
    )
    return WebCrawlError(error=envelope.error, meta=envelope.meta)


def _build_crawl_success_payload(
    *,
    validated_input: WebCrawlInput,
    final_url: HttpUrl | str,
    extraction_result: ExtractionResult,
    status_code: int,
    content_type: str,
    meta: ToolMeta,
    strategy_used: str = "http",
    escalation_count: int = 0,
    session_profile_id: str | None = None,
    block_reason: str | None = None,
    rendered: bool = False,
    challenge_detected: bool = False,
) -> WebCrawlSuccess:
    """Build typed crawl success output.

    Example input: `_build_crawl_success_payload(validated_input=WebCrawlInput(...), final_url="https://example.com", extraction_result=ExtractionResult(...), status_code=200, content_type="text/html", meta=ToolMeta(...))`
    Example output: `WebCrawlSuccess(status_code=200, strategy_used="http", ...)`
    """
    return WebCrawlSuccess(
        url=validated_input.url,
        final_url=final_url,
        text=extraction_result.text,
        markdown=extraction_result.markdown,
        objective=validated_input.objective,
        excerpts=extraction_result.excerpts,
        status_code=status_code,
        content_type=content_type,
        fallback_reason=extraction_result.fallback_reason,
        strategy_used=strategy_used,
        escalation_count=escalation_count,
        session_profile_id=session_profile_id,
        block_reason=block_reason,
        rendered=rendered,
        challenge_detected=challenge_detected,
        meta=meta,
    )


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


def _has_recovered_evidence(extraction_result: ExtractionResult) -> bool:
    """Report whether extracted crawl output contains usable evidence.

    Example input: `_has_recovered_evidence(ExtractionResult(state="ok", text="Summary", markdown="Summary"))`
    Example output: `True`
    """
    return bool(
        extraction_result.text
        or extraction_result.markdown
        or extraction_result.excerpts
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
    normalized_url = str(url).strip()

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
            "strategy_used": success.strategy_used,
            "escalation_count": success.escalation_count,
            "session_profile_id": success.session_profile_id,
            "rendered": success.rendered,
            "challenge_detected": success.challenge_detected,
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
