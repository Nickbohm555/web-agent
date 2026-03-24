import httpx

from backend.app.crawler.browser_worker import BrowserFetchSuccess
from backend.app.crawler.fetch_orchestrator import run_fetch_orchestrator
from backend.app.crawler.http_worker import HttpFetchWorker
from backend.app.crawler.schemas.browser_fetch import BrowserContextSeed, StorageStateApplied
from backend.app.crawler.schemas.session_profile import SessionProfile
from backend.app.crawler.session_profiles import InMemorySessionProfileProvider
from backend.app.tools.schemas.web_crawl import WebCrawlSuccess


def test_orchestrator_escalates_to_browser_for_403() -> None:
    worker = HttpFetchWorker(
        http_client=httpx.Client(
            transport=httpx.MockTransport(
                lambda request: httpx.Response(
                    403,
                    headers={"content-type": "text/html"},
                    text="<html><body>blocked</body></html>",
                    request=request,
                )
            ),
            follow_redirects=True,
        )
    )
    provider = InMemorySessionProfileProvider(
        profiles=[SessionProfile(profile_id="example-session", domains=["example.com"])]
    )

    payload = run_fetch_orchestrator(
        url="https://example.com/blocked",
        objective="Find pricing",
        fetch_worker=worker,
        session_profile_provider=provider,
        browser_fetcher=lambda *, url, seed: BrowserFetchSuccess(
            url=url,
            final_url=url,
            status_code=200,
            content_type="text/html",
            body=_rich_article_html(),
            seed_applied=StorageStateApplied(
                cookies=bool(seed.cookies),
                headers=bool(seed.headers),
                local_storage=bool(seed.local_storage),
                session_storage=bool(seed.session_storage),
            ),
        ),
    )
    result = WebCrawlSuccess.model_validate(payload)

    assert result.meta.strategy_used == "browser"
    assert result.meta.escalation_count == 1


def _rich_article_html() -> str:
    paragraphs = [
        "Session-aware crawling can recover evidence from rendered pages after the cheap HTTP path is blocked.",
        "Deterministic escalation keeps the crawl path auditable and avoids silent empty results.",
        "Browser-backed extraction should still feed the same typed success contract as the HTTP path.",
    ]
    article = "".join(f"<p>{paragraph}</p>" for paragraph in paragraphs)
    return f"""
    <html>
      <body>
        <main>
          <article>
            <h1>Browser fallback recovery</h1>
            {article}
          </article>
        </main>
      </body>
    </html>
    """
