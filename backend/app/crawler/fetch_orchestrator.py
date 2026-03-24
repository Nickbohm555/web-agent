from __future__ import annotations

from time import perf_counter
from typing import Callable, Optional

from backend.app.crawler.browser_worker import BrowserFetchResult, browser_fetch
from backend.app.crawler.content_normalizer import normalize_browser_fetch, normalize_http_fetch
from backend.app.crawler.error_mapping import map_browser_failure, map_crawl_failure
from backend.app.crawler.extractor import extract_content, extraction_result_from_fetch_failure
from backend.app.crawler.fetch_classification import classify_http_fetch
from backend.app.crawler.fetch_strategy import (
    decide_fetch_strategy,
    should_escalate_extraction,
    should_escalate_http_failure,
)
from backend.app.crawler.http_worker import HttpFetchFailure, HttpFetchWorker
from backend.app.crawler.schemas.browser_fetch import BrowserContextSeed, BrowserFetchFailure, BrowserFetchSuccess
from backend.app.crawler.schemas.session_profile import SessionProfile
from backend.app.crawler.session_profiles import SessionProfileProvider, get_session_profiles, resolve_session_profile
from backend.app.tools.schemas.tool_errors import ToolTimings
from backend.app.tools.schemas.web_crawl import WebCrawlMeta, WebCrawlSuccess, WebCrawlToolInput, WebCrawlToolResult

BrowserFetcher = Callable[..., BrowserFetchResult]


def run_fetch_orchestrator(
    *,
    url: str,
    fetch_worker: Optional[HttpFetchWorker] = None,
    session_profile_provider: Optional[SessionProfileProvider] = None,
    browser_fetcher: Optional[BrowserFetcher] = None,
) -> WebCrawlToolResult:
    validated_input = WebCrawlToolInput(url=url)
    operation_start = perf_counter()
    profiles = get_session_profiles(session_profile_provider)
    session_profile = resolve_session_profile(str(validated_input.url), profiles=profiles)
    strategy = decide_fetch_strategy(matched_profile=session_profile)

    if strategy.initial_mode == "browser":
        return _run_browser_path(
            validated_input=validated_input,
            session_profile=session_profile,
            browser_fetcher=browser_fetcher,
            escalation_count=0,
            block_reason="browser_only_profile",
            operation_start=operation_start,
        )

    http_result = (fetch_worker or HttpFetchWorker()).fetch(url=str(validated_input.url))
    if isinstance(http_result, HttpFetchFailure):
        if http_result.error.kind == "unsupported_content_type":
            return _build_success(
                validated_input=validated_input,
                final_url=http_result.final_url or str(validated_input.url),
                extraction_result=extraction_result_from_fetch_failure(http_result),
                status_code=http_result.status_code or 200,
                content_type=http_result.content_type or "application/octet-stream",
                strategy_used="http",
                escalation_count=0,
                session_profile=session_profile,
                rendered=False,
                challenge_detected=False,
                block_reason=None,
                total_ms=_elapsed_ms(operation_start),
            )

        if browser_fetcher is not None and should_escalate_http_failure(http_result, strategy=strategy):
            return _run_browser_path(
                validated_input=validated_input,
                session_profile=session_profile,
                browser_fetcher=browser_fetcher,
                escalation_count=1,
                block_reason=http_result.error.kind,
                operation_start=operation_start,
            )

        return map_crawl_failure(
            kind=http_result.error.kind,
            message=http_result.error.message,
            total_ms=_elapsed_ms(operation_start),
            retryable=http_result.error.retryable,
            status_code=http_result.error.status_code,
            attempt_number=http_result.error.attempt_number or 1,
            strategy_used="http",
            escalation_count=0,
            session_profile_id=session_profile.profile_id if session_profile is not None else None,
            block_reason=http_result.error.kind,
        )

    normalized_http = normalize_http_fetch(http_result)
    extraction_result = extract_content(
        body=normalized_http.body,
        content_type=normalized_http.content_type,
    )
    classification = classify_http_fetch(http_result, extraction_result=extraction_result)
    if browser_fetcher is not None and should_escalate_extraction(classification, strategy=strategy):
        return _run_browser_path(
            validated_input=validated_input,
            session_profile=session_profile,
            browser_fetcher=browser_fetcher,
            escalation_count=1,
            block_reason=classification.block_reason,
            operation_start=operation_start,
        )

    return _build_success(
        validated_input=validated_input,
        final_url=normalized_http.final_url,
        extraction_result=extraction_result,
        status_code=normalized_http.status_code,
        content_type=normalized_http.content_type,
        strategy_used="http",
        escalation_count=0,
        session_profile=session_profile,
        rendered=False,
        challenge_detected=False,
        block_reason=None,
        total_ms=_elapsed_ms(operation_start),
    )


def _run_browser_path(
    *,
    validated_input: WebCrawlToolInput,
    session_profile: Optional[SessionProfile],
    browser_fetcher: Optional[BrowserFetcher],
    escalation_count: int,
    block_reason: Optional[str],
    operation_start: float,
) -> WebCrawlToolResult:
    seed = _build_browser_context_seed(session_profile)
    result = browser_fetch(
        url=str(validated_input.url),
        seed=seed,
        fetch_impl=browser_fetcher,
    )
    if isinstance(result, BrowserFetchFailure):
        return map_browser_failure(
            result,
            total_ms=_elapsed_ms(operation_start),
            session_profile_id=session_profile.profile_id if session_profile is not None else None,
            escalation_count=escalation_count,
        )

    normalized_browser = normalize_browser_fetch(result)
    extraction_result = extract_content(
        body=normalized_browser.body,
        content_type=normalized_browser.content_type,
    )
    return _build_success(
        validated_input=validated_input,
        final_url=normalized_browser.final_url,
        extraction_result=extraction_result,
        status_code=normalized_browser.status_code,
        content_type=normalized_browser.content_type,
        strategy_used="browser",
        escalation_count=escalation_count,
        session_profile=session_profile,
        rendered=True,
        challenge_detected=False,
        block_reason=block_reason,
        total_ms=_elapsed_ms(operation_start),
    )


def _build_browser_context_seed(session_profile: Optional[SessionProfile]) -> BrowserContextSeed:
    if session_profile is None:
        return BrowserContextSeed()
    return BrowserContextSeed(
        cookies=session_profile.cookies,
        headers=session_profile.headers,
        local_storage=session_profile.local_storage,
        session_storage=session_profile.session_storage,
    )


def _build_success(
    *,
    validated_input: WebCrawlToolInput,
    final_url: str,
    extraction_result,
    status_code: int,
    content_type: str,
    strategy_used: str,
    escalation_count: int,
    session_profile: Optional[SessionProfile],
    rendered: bool,
    challenge_detected: bool,
    block_reason: Optional[str],
    total_ms: int,
) -> WebCrawlSuccess:
    return WebCrawlSuccess(
        url=validated_input.url,
        final_url=final_url,
        text=extraction_result.text,
        markdown=extraction_result.markdown,
        excerpts=extraction_result.excerpts,
        status_code=status_code,
        content_type=content_type,
        fallback_reason=extraction_result.fallback_reason,
        meta=WebCrawlMeta(
            operation="web_crawl",
            attempts=max(escalation_count + 1, 1),
            retries=max(escalation_count, 0),
            duration_ms=total_ms,
            timings=ToolTimings(total_ms=total_ms),
            strategy_used=strategy_used,
            escalation_count=escalation_count,
            session_profile_id=session_profile.profile_id if session_profile is not None else None,
            block_reason=block_reason,
            rendered=rendered,
            challenge_detected=challenge_detected,
        ),
    )


def _elapsed_ms(start: float) -> int:
    return int((perf_counter() - start) * 1000)
