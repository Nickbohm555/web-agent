from backend.app.crawler.schemas.session_profile import SessionProfile
from backend.app.crawler.session_profiles import (
    InMemorySessionProfileProvider,
    get_session_profiles,
    resolve_session_profile,
)


def test_resolve_session_profile_matches_domain() -> None:
    profile = resolve_session_profile(
        "https://app.example.com/settings",
        profiles=[
            SessionProfile(
                profile_id="example-session",
                domains=["example.com", "app.example.com"],
            )
        ],
    )

    assert profile is not None
    assert profile.profile_id == "example-session"


def test_get_session_profiles_returns_configured_profiles() -> None:
    provider = InMemorySessionProfileProvider(
        profiles=[SessionProfile(profile_id="example-session", domains=["example.com"])]
    )

    profiles = get_session_profiles(provider)

    assert profiles[0].profile_id == "example-session"
