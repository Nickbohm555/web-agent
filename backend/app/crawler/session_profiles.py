from __future__ import annotations

import json
import os
from pathlib import Path

from backend.app.crawler.schemas.session_profile import DomainSessionMatch, SessionProfile
from backend.app.tools._tool_utils import hostname_matches, normalize_hostname


def load_session_profiles(path: str | Path | None = None) -> list[SessionProfile]:
    resolved_path = _resolve_profiles_path(path)
    if resolved_path is None or not resolved_path.exists():
        return []

    payload = json.loads(resolved_path.read_text())
    return [SessionProfile.model_validate(entry) for entry in payload]


def resolve_domain_session_profile(
    url: str,
    *,
    profiles: list[SessionProfile] | None = None,
) -> DomainSessionMatch | None:
    hostname = normalize_hostname(url)
    if hostname is None:
        return None

    candidates: list[tuple[int, DomainSessionMatch]] = []
    for profile in profiles if profiles is not None else load_session_profiles():
        for domain in profile.domains:
            if hostname_matches(hostname, domain):
                candidates.append(
                    (
                        len(domain),
                        DomainSessionMatch(
                            matched_domain=domain,
                            profile=profile,
                        ),
                    )
                )

    if not candidates:
        return None

    return max(candidates, key=lambda item: item[0])[1]


def _resolve_profiles_path(path: str | Path | None) -> Path | None:
    if path is not None:
        return Path(path)

    configured_path = os.getenv("CRAWLER_SESSION_PROFILES_PATH")
    if not configured_path:
        return None

    return Path(configured_path)
