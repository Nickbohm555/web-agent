from __future__ import annotations

from time import perf_counter
from typing import Callable

from backend.app.crawler.schemas.browser_fetch import (
    BrowserContextSeed,
    BrowserFetchFailure,
    BrowserFetchSuccess,
)
from backend.app.crawler.schemas.session_profile import DomainSessionMatch
from backend.app.tools._tool_utils import build_tool_error_payload


class BrowserFetchWorker:
    def __init__(
        self,
        *,
        navigation_runner: Callable[..., BrowserFetchSuccess | BrowserFetchFailure] | None = None,
        timeout_ms: int = 10_000,
    ) -> None:
        self._navigation_runner = navigation_runner or _run_with_playwright
        self._timeout_ms = timeout_ms

    def fetch(
        self,
        *,
        url: str,
        session_match: DomainSessionMatch | None,
    ) -> BrowserFetchSuccess | BrowserFetchFailure:
        seed = _build_browser_context_seed(session_match)
        result = self._navigation_runner(
            url=url,
            seed=seed,
            timeout_ms=self._timeout_ms,
        )
        if isinstance(result, BrowserFetchSuccess) and result.meta is None:
            result = result.model_copy(
                update={"meta": _browser_meta(total_ms=0, status_code=result.status_code)}
            )
        return result


def _build_browser_context_seed(
    session_match: DomainSessionMatch | None,
) -> BrowserContextSeed:
    if session_match is None:
        return BrowserContextSeed()

    profile = session_match.profile
    return BrowserContextSeed(
        cookies=profile.cookies,
        extra_headers={header.name: header.value for header in profile.headers},
        local_storage={entry.key: entry.value for entry in profile.local_storage},
        session_storage={entry.key: entry.value for entry in profile.session_storage},
    )


def _run_with_playwright(
    *,
    url: str,
    seed: BrowserContextSeed,
    timeout_ms: int,
) -> BrowserFetchSuccess | BrowserFetchFailure:
    started_at = perf_counter()
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except Exception:
        return _build_browser_failure(
            url=url,
            kind="browser_navigation_failed",
            total_ms=_elapsed_ms(started_at),
            message="playwright is unavailable for browser navigation",
        )

    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            context = browser.new_context(extra_http_headers=seed.extra_headers or None)
            if seed.cookies:
                context.add_cookies(
                    [
                        {
                            "name": cookie.name,
                            "value": cookie.value,
                            "domain": cookie.domain,
                            "path": cookie.path,
                            "secure": cookie.secure,
                            "httpOnly": cookie.http_only,
                            **({"sameSite": cookie.same_site} if cookie.same_site else {}),
                            **({"expires": cookie.expires} if cookie.expires is not None else {}),
                        }
                        for cookie in seed.cookies
                    ]
                )
            if seed.local_storage or seed.session_storage:
                context.add_init_script(
                    _storage_seed_script(
                        local_storage=seed.local_storage,
                        session_storage=seed.session_storage,
                    )
                )

            page = context.new_page()
            response = page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            try:
                page.wait_for_load_state("networkidle", timeout=min(timeout_ms, 3_000))
            except PlaywrightTimeoutError:
                pass
            html = page.content()
            text = page.locator("body").inner_text()
            status_code = response.status if response is not None else 200
            content_type = (
                (response.headers.get("content-type") if response is not None else None)
                or "text/html"
            )
            final_url = page.url
            browser.close()
            return BrowserFetchSuccess(
                url=url,
                final_url=final_url,
                status_code=status_code,
                content_type=content_type.split(";", 1)[0].strip(),
                html=html,
                text=text,
                rendered=True,
                meta=_browser_meta(
                    total_ms=_elapsed_ms(started_at),
                    status_code=status_code,
                ),
            )
    except Exception:
        return _build_browser_failure(
            url=url,
            kind="browser_navigation_failed",
            total_ms=_elapsed_ms(started_at),
        )


def _storage_seed_script(
    *,
    local_storage: dict[str, str],
    session_storage: dict[str, str],
) -> str:
    local_lines = [
        f"window.localStorage.setItem({key!r}, {value!r});"
        for key, value in local_storage.items()
    ]
    session_lines = [
        f"window.sessionStorage.setItem({key!r}, {value!r});"
        for key, value in session_storage.items()
    ]
    return "\n".join([*local_lines, *session_lines])


def _build_browser_failure(
    *,
    url: str,
    kind: str,
    total_ms: int,
    message: str | None = None,
) -> BrowserFetchFailure:
    envelope = build_tool_error_payload(
        kind=kind,
        message=message or "browser navigation failed before evidence was recovered",
        retryable=False,
        total_ms=total_ms,
        operation="web_crawl",
    )
    return BrowserFetchFailure(
        url=url,
        error=envelope.error,
        meta=envelope.meta,
    )


def _browser_meta(*, total_ms: int, status_code: int) -> object:
    return build_tool_error_payload(
        kind="browser_navigation_success",
        message="browser navigation completed",
        retryable=False,
        total_ms=total_ms,
        operation="web_crawl",
        status_code=status_code,
    ).meta


def _elapsed_ms(started_at: float) -> int:
    return int((perf_counter() - started_at) * 1000)
