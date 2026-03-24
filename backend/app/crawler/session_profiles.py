from __future__ import annotations

from typing import Optional, Protocol, Sequence
from urllib.parse import urlsplit

from backend.app.crawler.schemas.session_profile import SessionProfile


class SessionProfileProvider(Protocol):
    def list_profiles(self) -> Sequence[SessionProfile]:
        ...


class InMemorySessionProfileProvider:
    def __init__(self, profiles: Sequence[SessionProfile]) -> None:
        self._profiles = list(profiles)

    def list_profiles(self) -> Sequence[SessionProfile]:
        return list(self._profiles)


def get_session_profiles(provider: Optional[SessionProfileProvider]) -> list[SessionProfile]:
    if provider is None:
        return []
    return list(provider.list_profiles())


def resolve_session_profile(
    url: str,
    *,
    profiles: Sequence[SessionProfile],
) -> Optional[SessionProfile]:
    hostname = _normalize_hostname(url)
    if hostname is None:
        return None

    best_profile: Optional[SessionProfile] = None
    best_score = -1
    best_index = len(profiles)

    for index, profile in enumerate(profiles):
        matched_domain = _best_matching_domain(hostname, profile.domains)
        if matched_domain is None:
            continue

        score = len(matched_domain)
        if score > best_score or (score == best_score and index < best_index):
            best_profile = profile
            best_score = score
            best_index = index

    return best_profile


def _best_matching_domain(hostname: str, domains: Sequence[str]) -> Optional[str]:
    best_domain: Optional[str] = None
    for domain in domains:
        normalized_domain = _normalize_hostname(domain)
        if normalized_domain is None:
            continue
        if _hostname_matches(hostname, normalized_domain):
            if best_domain is None or len(normalized_domain) > len(best_domain):
                best_domain = normalized_domain
    return best_domain


def _hostname_matches(hostname: str, domain: str) -> bool:
    return hostname == domain or hostname.endswith("." + domain)


def _normalize_hostname(value: str) -> Optional[str]:
    parsed = urlsplit(value if "://" in value else "https://" + value)
    hostname = parsed.hostname
    if hostname is None:
        return None
    return hostname.strip().lower()
