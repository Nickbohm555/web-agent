from __future__ import annotations

import re

from backend.app.crawler.schemas.fetch_strategy import (
    FetchClassification,
    FetchEscalationReason,
    FetchStrategyDecision,
)
from backend.app.crawler.schemas.http_fetch import HttpFetchFailure
from backend.app.crawler.schemas.session_profile import DomainSessionMatch
from backend.app.tools.schemas.web_crawl import ExtractionResult

_CHALLENGE_PATTERNS = (
    re.compile(r"captcha", re.IGNORECASE),
    re.compile(r"verify you are human", re.IGNORECASE),
    re.compile(r"access denied", re.IGNORECASE),
)
_JAVASCRIPT_PATTERNS = (
    re.compile(r"enable javascript", re.IGNORECASE),
    re.compile(r"id=['\"](?:root|__next|app)['\"]", re.IGNORECASE),
    re.compile(r"<script", re.IGNORECASE),
)


def decide_fetch_strategy(
    *,
    session_match: DomainSessionMatch | None,
) -> FetchStrategyDecision:
    if session_match is not None and session_match.profile.browser_only:
        return FetchStrategyDecision(
            strategy="browser",
            escalation_reason="browser_required",
        )
    return FetchStrategyDecision(strategy="http")


def classify_http_result(
    *,
    fetch_result: HttpFetchFailure | None,
    extraction_result: ExtractionResult | None,
    response_body: str | None = None,
) -> FetchClassification:
    if fetch_result is not None:
        if fetch_result.error.kind == "network_error":
            return "network_error"
        if fetch_result.error.kind == "unsupported_content_type":
            return "unsupported_content_type"
        if fetch_result.status_code == 401:
            return "auth_required"
        if fetch_result.status_code == 403:
            return "blocked"
        if _contains_challenge(fetch_result.error.message):
            return "challenge_detected"
        return "blocked"

    if extraction_result is None:
        return "low_content_quality"

    if extraction_result.state == "ok":
        return "success"
    if extraction_result.state == "unsupported-content-type":
        return "unsupported_content_type"
    if extraction_result.state == "network-error":
        return "network_error"
    if _looks_like_javascript_shell(response_body or extraction_result.text):
        return "javascript_required"
    return "low_content_quality"


def should_escalate_http_result(
    *,
    classification: FetchClassification,
) -> FetchEscalationReason | None:
    if classification == "auth_required":
        return "http_401"
    if classification == "blocked":
        return "http_403"
    if classification == "challenge_detected":
        return "challenge_detected"
    if classification == "low_content_quality":
        return "low_content_quality"
    if classification == "javascript_required":
        return "javascript_required"
    return None


def _contains_challenge(value: str | None) -> bool:
    if not value:
        return False
    return any(pattern.search(value) for pattern in _CHALLENGE_PATTERNS)


def _looks_like_javascript_shell(value: str | None) -> bool:
    if not value:
        return False
    return any(pattern.search(value) for pattern in _JAVASCRIPT_PATTERNS)
