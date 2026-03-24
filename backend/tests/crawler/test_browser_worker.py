from __future__ import annotations

from backend.app.crawler.browser_worker import BrowserFetchWorker
from backend.app.crawler.schemas.browser_fetch import BrowserFetchSuccess
from backend.app.crawler.schemas.session_profile import (
    DomainSessionMatch,
    SessionCookie,
    SessionHeader,
    SessionProfile,
    StorageSeedEntry,
)


def test_browser_worker_passes_seeded_session_state_to_navigation_runner() -> None:
    captured_seed: dict[str, object] = {}

    def navigation_runner(*, url: str, seed, timeout_ms: int):
        captured_seed["url"] = url
        captured_seed["seed"] = seed
        captured_seed["timeout_ms"] = timeout_ms
        return BrowserFetchSuccess(
            url=url,
            final_url=url,
            status_code=200,
            content_type="text/html",
            html="<html><body><main>Rendered evidence.</main></body></html>",
            text="Rendered evidence.",
            rendered=True,
        )

    worker = BrowserFetchWorker(navigation_runner=navigation_runner)
    match = DomainSessionMatch(
        matched_domain="app.example.com",
        profile=SessionProfile(
            id="authenticated-profile",
            domains=["app.example.com"],
            cookies=[
                SessionCookie(
                    name="sessionid",
                    value="abc123",
                    domain="app.example.com",
                )
            ],
            headers=[SessionHeader(name="x-test", value="worker")],
            local_storage=[StorageSeedEntry(key="featureFlag", value="on")],
            session_storage=[StorageSeedEntry(key="csrf", value="token")],
        ),
    )

    result = worker.fetch(url="https://app.example.com/dashboard", session_match=match)

    assert result.status_code == 200
    assert captured_seed["url"] == "https://app.example.com/dashboard"
    seed = captured_seed["seed"]
    assert seed.cookies[0].name == "sessionid"
    assert seed.extra_headers["x-test"] == "worker"
    assert seed.local_storage["featureFlag"] == "on"
    assert seed.session_storage["csrf"] == "token"
