from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

FetchClassification = Literal[
    "success",
    "blocked",
    "auth_required",
    "challenge_detected",
    "low_content_quality",
    "browser_navigation_failed",
    "session_profile_misconfigured",
    "unsupported_content_type",
    "network_error",
    "javascript_required",
]
FetchEscalationReason = Literal[
    "http_401",
    "http_403",
    "auth_required",
    "challenge_detected",
    "low_content_quality",
    "javascript_required",
    "browser_required",
]
FetchStrategy = Literal["http", "browser"]


class FetchStrategyDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    strategy: FetchStrategy
    escalation_reason: Optional[FetchEscalationReason] = None
