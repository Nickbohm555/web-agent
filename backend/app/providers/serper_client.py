from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from time import perf_counter
from typing import Any

import httpx

from backend.app.contracts.tool_errors import ToolMeta, ToolTimings
from backend.app.contracts.web_search import SearchMetadata, SearchRank, WebSearchResponse, WebSearchResult
from backend.app.core.retry import execute_with_retry

SERPER_SEARCH_URL = "https://google.serper.dev/search"
DEFAULT_TIMEOUT = httpx.Timeout(5.0, connect=2.0)


@dataclass
class SerperClientError(Exception):
    kind: str
    message: str
    retryable: bool
    status_code: int | None = None
    attempt_number: int | None = None
    operation: str = "web_search"
    provider_ms: int | None = None

    def __str__(self) -> str:
        return self.message


class RetryableSerperError(SerperClientError):
    def __init__(
        self,
        *,
        kind: str,
        message: str,
        status_code: int | None = None,
        attempt_number: int | None = None,
        provider_ms: int | None = None,
    ) -> None:
        super().__init__(
            kind=kind,
            message=message,
            retryable=True,
            status_code=status_code,
            attempt_number=attempt_number,
            provider_ms=provider_ms,
        )


class NonRetryableSerperError(SerperClientError):
    def __init__(
        self,
        *,
        kind: str,
        message: str,
        status_code: int | None = None,
        attempt_number: int | None = None,
        provider_ms: int | None = None,
    ) -> None:
        super().__init__(
            kind=kind,
            message=message,
            retryable=False,
            status_code=status_code,
            attempt_number=attempt_number,
            provider_ms=provider_ms,
        )


class SerperClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = SERPER_SEARCH_URL,
        timeout: httpx.Timeout = DEFAULT_TIMEOUT,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._timeout = timeout
        self._http_client = http_client

    def search(
        self,
        *,
        query: str,
        max_results: int,
        freshness: str = "any",
    ) -> WebSearchResponse:
        normalized_query = query.strip()
        if not normalized_query:
            raise NonRetryableSerperError(
                kind="invalid_request",
                message="query must not be blank",
                attempt_number=1,
            )

        operation_start = perf_counter()
        cumulative_provider_ms = 0

        def perform_request(attempt_number: int) -> dict[str, Any]:
            nonlocal cumulative_provider_ms
            request_start = perf_counter()
            try:
                payload = {"q": normalized_query, "num": max_results}
                freshness_tbs = _map_freshness_to_tbs(freshness)
                if freshness_tbs is not None:
                    payload["tbs"] = freshness_tbs
                response = self._post(payload)
            except httpx.RequestError as exc:
                provider_ms = _elapsed_ms(request_start)
                cumulative_provider_ms += provider_ms
                raise RetryableSerperError(
                    kind="provider_unavailable",
                    message="serper request failed",
                    attempt_number=attempt_number,
                    provider_ms=provider_ms,
                ) from exc

            provider_ms = _elapsed_ms(request_start)
            cumulative_provider_ms += provider_ms
            return self._parse_response(response, attempt_number=attempt_number, provider_ms=provider_ms)

        result = execute_with_retry(
            perform_request,
            retryable_exceptions=(RetryableSerperError,),
            max_attempts=3,
        )
        total_ms = _elapsed_ms(operation_start)
        results = _normalize_results(result.value, max_results=max_results)
        return WebSearchResponse(
            query=normalized_query,
            results=results,
            metadata=SearchMetadata(result_count=len(results), provider="serper"),
            meta=ToolMeta(
                operation="web_search",
                attempts=result.attempts,
                retries=result.attempts - 1,
                duration_ms=total_ms,
                timings=ToolTimings(total_ms=total_ms, provider_ms=cumulative_provider_ms),
            ),
        )

    def _parse_response(
        self, response: httpx.Response, *, attempt_number: int, provider_ms: int
    ) -> dict[str, Any]:
        status_code = response.status_code
        if status_code == 429:
            raise RetryableSerperError(
                kind="provider_rate_limited",
                message="serper rate limited the request",
                status_code=status_code,
                attempt_number=attempt_number,
                provider_ms=provider_ms,
            )
        if status_code >= 500:
            raise RetryableSerperError(
                kind="provider_unavailable",
                message="serper upstream failure",
                status_code=status_code,
                attempt_number=attempt_number,
                provider_ms=provider_ms,
            )
        if 400 <= status_code < 500:
            raise NonRetryableSerperError(
                kind="invalid_request",
                message="serper rejected the request",
                status_code=status_code,
                attempt_number=attempt_number,
                provider_ms=provider_ms,
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise RetryableSerperError(
                kind="provider_unavailable",
                message="serper returned invalid json",
                status_code=status_code,
                attempt_number=attempt_number,
                provider_ms=provider_ms,
            ) from exc

        if not isinstance(payload, dict):
            raise RetryableSerperError(
                kind="provider_unavailable",
                message="serper returned an invalid payload",
                status_code=status_code,
                attempt_number=attempt_number,
                provider_ms=provider_ms,
            )
        return payload

    def _post(self, payload: dict[str, Any]) -> httpx.Response:
        headers = {
            "x-api-key": self._api_key,
            "content-type": "application/json",
        }
        if self._http_client is not None:
            return self._http_client.post(
                self._base_url,
                headers=headers,
                json=payload,
                timeout=self._timeout,
            )

        with httpx.Client() as client:
            return client.post(
                self._base_url,
                headers=headers,
                json=payload,
                timeout=self._timeout,
            )


def _normalize_results(payload: dict[str, Any], *, max_results: int) -> list[WebSearchResult]:
    organic = payload.get("organic", [])
    if not isinstance(organic, Iterable) or isinstance(organic, (str, bytes, dict)):
        organic = []

    normalized: list[tuple[int, dict[str, Any]]] = []
    for fallback_position, raw_item in enumerate(organic, start=1):
        if not isinstance(raw_item, dict):
            continue
        title = _clean_text(raw_item.get("title"))
        url = _clean_text(raw_item.get("link"))
        snippet = _build_provider_snippet(raw_item)
        if not title or not url:
            continue
        provider_position = raw_item.get("position")
        normalized_position = (
            provider_position
            if isinstance(provider_position, int) and provider_position >= 1
            else fallback_position
        )
        normalized.append(
            (
                normalized_position,
                {"title": title, "url": url, "snippet": snippet},
            )
        )

    normalized.sort(key=lambda item: item[0])

    results: list[WebSearchResult] = []
    for position, (provider_position, item) in enumerate(normalized[:max_results], start=1):
        results.append(
            WebSearchResult(
                title=item["title"],
                url=item["url"],
                snippet=item["snippet"],
                rank=SearchRank(position=position, provider_position=provider_position),
            )
        )
    return results


def _build_provider_snippet(raw_item: dict[str, Any]) -> str:
    parts: list[str] = []

    snippet = _clean_text(raw_item.get("snippet"), allow_empty=True)
    if snippet:
        parts.append(snippet)

    date = _clean_text(raw_item.get("date"), allow_empty=True)
    if date:
        parts.append(f"Published: {date}")

    attributes = raw_item.get("attributes")
    if isinstance(attributes, dict):
        for key, value in attributes.items():
            normalized_key = _clean_text(key, allow_empty=True)
            normalized_value = _clean_text(value, allow_empty=True)
            if normalized_key and normalized_value:
                parts.append(f"{normalized_key}: {normalized_value}")

    return _dedupe_parts(parts)


def _dedupe_parts(parts: Iterable[str]) -> str:
    unique_parts: list[str] = []
    seen: set[str] = set()

    for part in parts:
        normalized = _clean_text(part, allow_empty=True)
        if not normalized:
            continue
        lowered = normalized.casefold()
        if lowered in seen:
            continue
        seen.add(lowered)
        unique_parts.append(normalized)

    return " | ".join(unique_parts)


def _clean_text(value: Any, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        return ""
    text = value.strip()
    if text or allow_empty:
        return text
    return ""


def _elapsed_ms(start: float) -> int:
    return int((perf_counter() - start) * 1000)


def _map_freshness_to_tbs(freshness: str) -> str | None:
    return {
        "day": "qdr:d",
        "week": "qdr:w",
        "month": "qdr:m",
        "year": "qdr:y",
    }.get(freshness)
