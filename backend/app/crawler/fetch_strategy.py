from __future__ import annotations

from typing import Optional

from backend.app.crawler.fetch_classification import classify_http_failure
from backend.app.crawler.http_worker import HttpFetchFailure
from backend.app.crawler.schemas.fetch_strategy import FetchClassification, FetchStrategyDecision
from backend.app.crawler.schemas.session_profile import SessionProfile


def decide_fetch_strategy(
    *,
    matched_profile: Optional[SessionProfile] = None,
) -> FetchStrategyDecision:
    if matched_profile is not None and matched_profile.browser_only:
        return FetchStrategyDecision(
            initial_mode="browser",
            should_try_browser_escalation=False,
            escalation_reason="browser_only_profile",
        )

    return FetchStrategyDecision(
        initial_mode="http",
        should_try_browser_escalation=True,
    )


def should_escalate_http_failure(
    failure: HttpFetchFailure,
    *,
    strategy: FetchStrategyDecision,
) -> bool:
    if not strategy.should_try_browser_escalation:
        return False

    classification = classify_http_failure(failure)
    return classification.kind in {"blocked", "auth_required", "challenge_detected"}


def should_escalate_extraction(
    classification: FetchClassification,
    *,
    strategy: FetchStrategyDecision,
) -> bool:
    return strategy.should_try_browser_escalation and classification.kind == "low_content_quality"
