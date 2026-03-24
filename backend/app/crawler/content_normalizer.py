from __future__ import annotations

from backend.app.crawler.schemas.browser_fetch import BrowserFetchSuccess
from backend.app.crawler.schemas.http_fetch import HttpFetchSuccess


def normalize_http_content(fetch_result: HttpFetchSuccess) -> tuple[str, str]:
    return fetch_result.body, fetch_result.content_type


def normalize_browser_content(fetch_result: BrowserFetchSuccess) -> tuple[str, str]:
    body = fetch_result.html.strip() or fetch_result.text.strip()
    return body, fetch_result.content_type
