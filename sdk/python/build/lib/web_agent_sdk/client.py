from __future__ import annotations

from typing import Any

import httpx

from .errors import WebAgentSdkError
from .schemas.agentic_search import AgenticSearchRequest, AgenticSearchResponse
from .schemas.quick_search import QuickSearchOptions, QuickSearchRequest, QuickSearchResponse


class WebAgentClient:
    def __init__(
        self,
        *,
        base_url: str,
        backend_base_url: str | None = None,
        timeout: float = 30.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._backend_base_url = (backend_base_url or base_url).rstrip("/")
        self._owns_http_client = http_client is None
        self._http_client = http_client or httpx.Client(timeout=timeout)

    def close(self) -> None:
        if self._owns_http_client:
            self._http_client.close()

    def quick_search(
        self,
        query: str,
        *,
        max_results: int | None = None,
        options: QuickSearchOptions | None = None,
    ) -> QuickSearchResponse:
        resolved_options = options or QuickSearchOptions()
        if max_results is not None:
            resolved_options = resolved_options.model_copy(update={"max_results": max_results})
        request = QuickSearchRequest(query=query, options=resolved_options)
        response = self._http_client.post(
            f"{self._base_url}/api/search",
            json=request.model_dump(mode="json", by_alias=True, exclude_none=True),
        )
        payload = self._read_json(response)
        if response.is_success:
            return QuickSearchResponse.model_validate(self._require_data_envelope(payload))
        self._raise_sdk_error(response, payload)

    def agentic_search(
        self,
        prompt: str,
        *,
        thread_id: str | None = None,
    ) -> AgenticSearchResponse:
        request = AgenticSearchRequest(prompt=prompt, thread_id=thread_id)
        response = self._http_client.post(
            f"{self._backend_base_url}/api/agent/run",
            json=request.model_dump(mode="json", exclude_none=True),
        )
        payload = self._read_json(response)
        if response.is_success:
            return AgenticSearchResponse.model_validate(payload)
        self._raise_sdk_error(response, payload)

    def _read_json(self, response: httpx.Response) -> Any:
        try:
            return response.json()
        except ValueError:
            return None

    def _require_data_envelope(self, payload: Any) -> Any:
        if isinstance(payload, dict) and payload.get("ok") is True and "data" in payload:
            return payload["data"]
        raise WebAgentSdkError(
            "Search response did not include a success data envelope.",
            status_code=200,
            code="INVALID_RESPONSE",
            retryable=False,
        )

    def _raise_sdk_error(self, response: httpx.Response, payload: Any) -> None:
        error_payload = payload.get("error") if isinstance(payload, dict) else None
        if isinstance(error_payload, dict):
            raise WebAgentSdkError(
                str(error_payload.get("message") or f"Request failed with status {response.status_code}."),
                status_code=response.status_code,
                code=str(error_payload.get("code")) if error_payload.get("code") is not None else None,
                retryable=(
                    bool(error_payload.get("retryable"))
                    if error_payload.get("retryable") is not None
                    else None
                ),
            )
        raise WebAgentSdkError(
            f"Request failed with status {response.status_code}.",
            status_code=response.status_code,
            code=None,
            retryable=None,
        )


def quick_search(
    query: str,
    *,
    base_url: str,
    backend_base_url: str | None = None,
    max_results: int | None = None,
    options: QuickSearchOptions | None = None,
    timeout: float = 30.0,
) -> QuickSearchResponse:
    client = WebAgentClient(
        base_url=base_url,
        backend_base_url=backend_base_url,
        timeout=timeout,
    )
    try:
        return client.quick_search(query, max_results=max_results, options=options)
    finally:
        client.close()


def agentic_search(
    prompt: str,
    *,
    base_url: str,
    backend_base_url: str | None = None,
    thread_id: str | None = None,
    timeout: float = 30.0,
) -> AgenticSearchResponse:
    client = WebAgentClient(
        base_url=base_url,
        backend_base_url=backend_base_url,
        timeout=timeout,
    )
    try:
        return client.agentic_search(prompt, thread_id=thread_id)
    finally:
        client.close()
