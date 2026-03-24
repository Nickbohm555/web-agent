from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from backend.app.crawler.http_worker import HttpFetchSuccess
from backend.app.crawler.schemas.browser_fetch import BrowserFetchSuccess


class NormalizedContent(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    body: str
    content_type: str
    final_url: str
    status_code: int
    rendered: bool


def normalize_http_fetch(fetch_result: HttpFetchSuccess) -> NormalizedContent:
    return NormalizedContent(
        body=fetch_result.body,
        content_type=fetch_result.content_type,
        final_url=fetch_result.final_url,
        status_code=fetch_result.status_code,
        rendered=False,
    )


def normalize_browser_fetch(fetch_result: BrowserFetchSuccess) -> NormalizedContent:
    return NormalizedContent(
        body=fetch_result.body,
        content_type=fetch_result.content_type,
        final_url=fetch_result.final_url,
        status_code=fetch_result.status_code,
        rendered=True,
    )
