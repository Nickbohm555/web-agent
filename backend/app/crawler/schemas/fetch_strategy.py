from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

FetchMode = Literal["http", "browser"]
FetchEscalationReason = Literal[
    "http_status",
    "blocked",
    "auth_required",
    "challenge_detected",
    "low_content_quality",
    "browser_only_profile",
]
FetchClassificationKind = Literal[
    "ok",
    "blocked",
    "auth_required",
    "challenge_detected",
    "low_content_quality",
    "unsupported_content_type",
    "network_error",
]


class FetchClassification(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    kind: FetchClassificationKind
    block_reason: Optional[str] = None
    challenge_detected: bool = False


class FetchStrategyDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    initial_mode: FetchMode
    should_try_browser_escalation: bool
    escalation_reason: Optional[FetchEscalationReason] = None
