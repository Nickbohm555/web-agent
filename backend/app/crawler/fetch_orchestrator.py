from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from backend.app.crawler.browser_worker import BrowserFetchWorker
from backend.app.crawler.content_normalizer import normalize_browser_content, normalize_http_content
from backend.app.crawler.error_mapping import map_classification_error
from backend.app.crawler.extractor import extract_content
from backend.app.crawler.fetch_strategy import (
    classify_http_result,
    decide_fetch_strategy,
    should_escalate_http_result,
)
from backend.app.crawler.http_worker import HttpFetchWorker
from backend.app.crawler.schemas.browser_fetch import BrowserFetchFailure
from backend.app.crawler.schemas.http_fetch import HttpFetchFailure, HttpFetchSuccess
from backend.app.crawler.schemas.session_profile import DomainSessionMatch, SessionProfile
from backend.app.crawler.session_profiles import resolve_domain_session_profile
from backend.app.tools.schemas.tool_errors import ToolMeta
from backend.app.tools.schemas.web_crawl import ExtractionResult, WebCrawlError


@dataclass(frozen=True)
class CrawlSuccessEnvelope:
    final_url: str
    status_code: int
    content_type: str
    extraction_result: ExtractionResult
    meta: ToolMeta
    strategy_used: str
    escalation_count: int
    session_profile_id: str | None
    block_reason: str | None
    rendered: bool
    challenge_detected: bool


class FetchOrchestrator:
    def __init__(
        self,
        *,
        http_fetch_worker: HttpFetchWorker | None = None,
        browser_fetch_worker: BrowserFetchWorker | None = None,
        session_profiles: list[SessionProfile] | None = None,
    ) -> None:
        self._http_fetch_worker = http_fetch_worker or HttpFetchWorker()
        self._browser_fetch_worker = browser_fetch_worker or BrowserFetchWorker()
        self._session_profiles = session_profiles

    def crawl(
        self,
        *,
        url: str,
        objective: str | None,
    ) -> CrawlSuccessEnvelope | WebCrawlError:
        started_at = perf_counter()
        session_match = resolve_domain_session_profile(url, profiles=self._session_profiles)
        decision = decide_fetch_strategy(session_match=session_match)
        if decision.strategy == "browser":
            return self._crawl_with_browser(
                url=url,
                objective=objective,
                session_match=session_match,
                escalation_count=0,
                started_at=started_at,
            )

        http_result = self._http_fetch_worker.fetch(url=url)
        if isinstance(http_result, HttpFetchFailure):
            if http_result.error.kind not in {"network_error", "unsupported_content_type"} and (
                http_result.status_code not in {401, 403}
            ):
                return WebCrawlError(error=http_result.error, meta=http_result.meta)
            classification = classify_http_result(
                fetch_result=http_result,
                extraction_result=None,
            )
            if should_escalate_http_result(classification=classification) is not None:
                return self._crawl_with_browser(
                    url=url,
                    objective=objective,
                    session_match=session_match,
                    escalation_count=1,
                    started_at=started_at,
                    block_reason=classification,
                    challenge_detected=classification == "challenge_detected",
                )
            return WebCrawlError(error=http_result.error, meta=http_result.meta)

        return self._finish_http_result(
            fetch_result=http_result,
            objective=objective,
            session_match=session_match,
            url=url,
            started_at=started_at,
        )

    def _finish_http_result(
        self,
        *,
        fetch_result: HttpFetchSuccess,
        objective: str | None,
        session_match: DomainSessionMatch | None,
        url: str,
        started_at: float,
    ) -> CrawlSuccessEnvelope | WebCrawlError:
        body, content_type = normalize_http_content(fetch_result)
        extraction_result = extract_content(
            body=body,
            content_type=content_type,
            objective=objective,
        )
        classification = classify_http_result(
            fetch_result=None,
            extraction_result=extraction_result,
            response_body=body,
        )
        if classification == "success":
            return CrawlSuccessEnvelope(
                final_url=fetch_result.final_url,
                status_code=fetch_result.status_code,
                content_type=fetch_result.content_type,
                extraction_result=extraction_result,
                meta=fetch_result.meta,
                strategy_used="http",
                escalation_count=0,
                session_profile_id=session_match.profile.id if session_match is not None else None,
                block_reason=None,
                rendered=False,
                challenge_detected=False,
            )

        if should_escalate_http_result(classification=classification) is not None:
            return self._crawl_with_browser(
                url=url,
                objective=objective,
                session_match=session_match,
                escalation_count=1,
                started_at=started_at,
                block_reason=classification,
                challenge_detected=classification == "challenge_detected",
            )

        return map_classification_error(
            kind=classification,
            total_ms=fetch_result.meta.duration_ms,
            status_code=fetch_result.status_code,
            attempt_number=fetch_result.meta.attempts,
        )

    def _crawl_with_browser(
        self,
        *,
        url: str,
        objective: str | None,
        session_match: DomainSessionMatch | None,
        escalation_count: int,
        started_at: float,
        block_reason: str | None = None,
        challenge_detected: bool = False,
    ) -> CrawlSuccessEnvelope | WebCrawlError:
        browser_result = self._browser_fetch_worker.fetch(
            url=url,
            session_match=session_match,
        )
        if isinstance(browser_result, BrowserFetchFailure):
            return map_classification_error(
                kind="browser_navigation_failed",
                total_ms=_elapsed_ms(started_at),
                status_code=browser_result.status_code,
                attempt_number=browser_result.meta.attempts,
                message=browser_result.error.message,
            )

        body, content_type = normalize_browser_content(browser_result)
        extraction_result = extract_content(
            body=body,
            content_type=content_type,
            objective=objective,
        )
        if extraction_result.state != "ok":
            classification = classify_http_result(
                fetch_result=None,
                extraction_result=extraction_result,
                response_body=body,
            )
            return map_classification_error(
                kind=classification,
                total_ms=_elapsed_ms(started_at),
                status_code=browser_result.status_code,
                attempt_number=1 + escalation_count,
            )

        return CrawlSuccessEnvelope(
            final_url=browser_result.final_url,
            status_code=browser_result.status_code,
            content_type=browser_result.content_type,
            extraction_result=extraction_result,
            meta=_with_total_duration(browser_result.meta, _elapsed_ms(started_at)),
            strategy_used="browser",
            escalation_count=escalation_count,
            session_profile_id=session_match.profile.id if session_match is not None else None,
            block_reason=block_reason,
            rendered=browser_result.rendered,
            challenge_detected=challenge_detected,
        )


def _with_total_duration(meta: ToolMeta | None, total_ms: int) -> ToolMeta:
    if meta is None:
        raise ValueError("browser success must include tool metadata")
    return meta.model_copy(
        update={
            "duration_ms": total_ms,
            "timings": meta.timings.model_copy(update={"total_ms": total_ms}),
        }
    )


def _elapsed_ms(started_at: float) -> int:
    return int((perf_counter() - started_at) * 1000)
