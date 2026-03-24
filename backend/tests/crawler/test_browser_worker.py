from backend.app.crawler.browser_worker import browser_fetch
from backend.app.crawler.schemas.browser_fetch import BrowserContextSeed, StorageStateApplied


def test_browser_worker_applies_seeded_session_state() -> None:
    result = browser_fetch(
        url="https://example.com/dashboard",
        seed=BrowserContextSeed(
            cookies=[
                {
                    "name": "sessionid",
                    "value": "cookie-value",
                    "domain": "example.com",
                }
            ],
            headers={"x-test-header": "1"},
            local_storage=[{"name": "featureFlag", "value": "enabled"}],
            session_storage=[{"name": "csrfToken", "value": "abc123"}],
        ),
        fetch_impl=lambda url, seed: {
            "url": url,
            "final_url": url,
            "status_code": 200,
            "content_type": "text/html",
            "body": "<html><body><article>Hello browser world.</article></body></html>",
            "seed_applied": StorageStateApplied(
                cookies=bool(seed.cookies),
                headers=bool(seed.headers),
                local_storage=bool(seed.local_storage),
                session_storage=bool(seed.session_storage),
            ),
        },
    )

    assert result.seed_applied.cookies is True
    assert result.seed_applied.headers is True
    assert result.seed_applied.local_storage is True
    assert result.seed_applied.session_storage is True
