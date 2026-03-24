from __future__ import annotations

from backend.app.crawler.schemas.fetch_strategy import (
    FetchStrategyDecision,
)
from backend.app.crawler.fetch_classification import (
    classify_http_result,
    should_escalate_http_result,
)
from backend.app.crawler.schemas.session_profile import DomainSessionMatch


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
