from __future__ import annotations

import json

from backend.app.crawler.session_profiles import (
    load_session_profiles,
    resolve_domain_session_profile,
)


def test_load_session_profiles_and_resolve_best_domain_match(tmp_path) -> None:
    config_path = tmp_path / "session_profiles.json"
    config_path.write_text(
        json.dumps(
            [
                {
                    "id": "broad-profile",
                    "domains": ["example.com"],
                    "headers": [{"name": "x-test", "value": "broad"}],
                },
                {
                    "id": "exact-profile",
                    "domains": ["dashboard.example.com"],
                    "browser_only": True,
                    "cookies": [
                        {
                            "name": "sessionid",
                            "value": "abc123",
                            "domain": "dashboard.example.com",
                        }
                    ],
                },
            ]
        )
    )

    profiles = load_session_profiles(config_path)
    match = resolve_domain_session_profile(
        "https://dashboard.example.com/settings",
        profiles=profiles,
    )

    assert match is not None
    assert match.profile.id == "exact-profile"
    assert match.matched_domain == "dashboard.example.com"
    assert match.profile.browser_only is True


def test_resolve_domain_session_profile_returns_none_without_match() -> None:
    assert (
        resolve_domain_session_profile(
            "https://outside.example.net/page",
            profiles=[],
        )
        is None
    )
