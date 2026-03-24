from __future__ import annotations

from backend.app.crawler.schemas.browser_fetch import BrowserFetchSuccess
from backend.app.crawler.schemas.http_fetch import HttpFetchSuccess
from backend.app.tools.schemas.web_crawl import NormalizedCrawlContent


def normalize_http_content(fetch_result: HttpFetchSuccess) -> NormalizedCrawlContent:
    return NormalizedCrawlContent(
        url=fetch_result.url,
        final_url=fetch_result.final_url,
        status_code=fetch_result.status_code,
        content_type=fetch_result.content_type,
        body=fetch_result.body,
        source="http",
        rendered=False,
    )


def normalize_browser_content(fetch_result: BrowserFetchSuccess) -> NormalizedCrawlContent:
    normalized_html = fetch_result.html.strip()
    normalized_text = fetch_result.text.strip()
    return NormalizedCrawlContent(
        url=fetch_result.url,
        final_url=fetch_result.final_url,
        status_code=fetch_result.status_code,
        content_type=fetch_result.content_type,
        body=normalized_html or normalized_text,
        source="browser",
        rendered=fetch_result.rendered,
        raw_html=normalized_html or None,
        extracted_text=normalized_text or None,
    )
