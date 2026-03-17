import httpx
import pytest
from pydantic import ValidationError

from backend.app.contracts.tool_errors import ToolError, ToolErrorEnvelope, ToolMeta, ToolTimings
from backend.app.contracts.web_search import (
    SearchMetadata,
    SearchRank,
    WebSearchInput,
    WebSearchResponse,
    WebSearchResult,
)
from backend.app.providers.serper_client import (
    NonRetryableSerperError,
    RetryableSerperError,
    SerperClient,
)


def test_web_search_input_normalizes_query_and_bounds_max_results() -> None:
    model = WebSearchInput(query="  agents  ", max_results=3)

    assert model.query == "agents"
    assert model.max_results == 3


@pytest.mark.parametrize(
    ("payload", "field_name"),
    [
        ({"query": "   ", "max_results": 3}, "query"),
        ({"query": "agents", "max_results": 0}, "max_results"),
        ({"query": "agents", "max_results": 11}, "max_results"),
        ({"query": "agents", "max_results": "3"}, "max_results"),
    ],
)
def test_web_search_input_rejects_invalid_payloads(payload: dict[str, object], field_name: str) -> None:
    with pytest.raises(ValidationError) as exc_info:
        WebSearchInput(**payload)

    assert field_name in str(exc_info.value)


def test_web_search_response_accepts_normalized_success_payload() -> None:
    response = WebSearchResponse(
        query="  agents  ",
        results=[
            WebSearchResult(
                title="Example result",
                url="https://example.com/article",
                snippet="  Summary text.  ",
                rank=SearchRank(position=1, provider_position=2),
            )
        ],
        metadata=SearchMetadata(result_count=1, provider="serper"),
        meta=ToolMeta(
            operation="web_search",
            attempts=2,
            retries=1,
            duration_ms=120,
            timings=ToolTimings(total_ms=120, provider_ms=95),
        ),
    )

    assert response.query == "agents"
    assert response.results[0].snippet == "Summary text."
    assert str(response.results[0].url) == "https://example.com/article"
    assert response.metadata.result_count == 1


@pytest.mark.parametrize(
    ("payload", "field_name"),
    [
        (
            {
                "query": "agents",
                "results": [
                    {
                        "title": "Result",
                        "url": "not-a-url",
                        "snippet": "Summary",
                        "rank": {"position": 1, "provider_position": 1},
                    }
                ],
                "metadata": {"result_count": 1, "provider": "serper"},
                "meta": {
                    "operation": "web_search",
                    "attempts": 1,
                    "retries": 0,
                    "duration_ms": 10,
                    "timings": {"total_ms": 10, "provider_ms": 8},
                },
            },
            "url",
        ),
        (
            {
                "query": "agents",
                "results": [
                    {
                        "title": "Result",
                        "url": "https://example.com/article",
                        "snippet": "Summary",
                        "rank": {"position": 0, "provider_position": 1},
                    }
                ],
                "metadata": {"result_count": 1, "provider": "serper"},
                "meta": {
                    "operation": "web_search",
                    "attempts": 1,
                    "retries": 0,
                    "duration_ms": 10,
                    "timings": {"total_ms": 10, "provider_ms": 8},
                },
            },
            "position",
        ),
        (
            {
                "query": "agents",
                "results": [],
                "metadata": {"result_count": 1, "provider": "serper"},
                "meta": {
                    "operation": "web_search",
                    "attempts": 1,
                    "retries": 0,
                    "duration_ms": 10,
                    "timings": {"total_ms": 10, "provider_ms": 8},
                },
            },
            "result_count",
        ),
    ],
)
def test_web_search_response_rejects_invalid_payloads(
    payload: dict[str, object], field_name: str
) -> None:
    with pytest.raises(ValidationError) as exc_info:
        WebSearchResponse(**payload)

    assert field_name in str(exc_info.value)


def test_tool_error_envelope_accepts_retryable_error_details() -> None:
    envelope = ToolErrorEnvelope(
        error=ToolError(
            kind="provider_unavailable",
            message="Temporary upstream failure",
            retryable=True,
            status_code=503,
            attempt_number=2,
            operation="web_search",
            timings=ToolTimings(total_ms=400, provider_ms=380),
        ),
        meta=ToolMeta(
            operation="web_search",
            attempts=2,
            retries=1,
            duration_ms=400,
            timings=ToolTimings(total_ms=400, provider_ms=380),
        ),
    )

    assert envelope.error.retryable is True
    assert envelope.error.attempt_number == 2
    assert envelope.meta.retries == 1


@pytest.mark.parametrize(
    ("payload", "field_name"),
    [
        (
            {
                "error": {
                    "kind": "provider_unavailable",
                    "message": "Temporary upstream failure",
                    "retryable": True,
                    "status_code": 503,
                    "operation": "web_search",
                },
                "meta": {
                    "operation": "web_search",
                    "attempts": 1,
                    "retries": 0,
                    "duration_ms": 400,
                    "timings": {"total_ms": 400, "provider_ms": 380},
                },
            },
            "attempt_number",
        ),
        (
            {
                "error": {
                    "kind": "provider_unavailable",
                    "message": "",
                    "retryable": False,
                    "operation": "web_search",
                },
                "meta": {
                    "operation": "web_search",
                    "attempts": 1,
                    "retries": 0,
                    "duration_ms": 400,
                    "timings": {"total_ms": 400, "provider_ms": 380},
                },
            },
            "message",
        ),
        (
            {
                "error": {
                    "kind": "provider_unavailable",
                    "message": "Bad request",
                    "retryable": False,
                    "status_code": 99,
                    "operation": "web_search",
                },
                "meta": {
                    "operation": "web_search",
                    "attempts": 0,
                    "retries": 0,
                    "duration_ms": 400,
                    "timings": {"total_ms": 400, "provider_ms": 380},
                },
            },
            "status_code",
        ),
    ],
)
def test_tool_error_envelope_rejects_invalid_payloads(
    payload: dict[str, object], field_name: str
) -> None:
    with pytest.raises(ValidationError) as exc_info:
        ToolErrorEnvelope(**payload)

    assert field_name in str(exc_info.value)


def test_serper_client_returns_normalized_results_on_success() -> None:
    captured_request: dict[str, object] = {}

    def handler(request):
        captured_request["headers"] = dict(request.headers)
        captured_request["json"] = request.read().decode("utf-8")
        return _json_response(
            200,
            {
                "organic": [
                    {
                        "title": "Second result",
                        "link": "https://example.com/two",
                        "snippet": "Second snippet",
                        "position": 2,
                    },
                    {
                        "title": "First result",
                        "link": "https://example.com/one",
                        "snippet": "First snippet",
                        "position": 1,
                    },
                ]
            },
        )

    client = SerperClient(
        api_key="serper-test-key",
        http_client=_mock_http_client(handler),
    )

    response = client.search(query="  agents  ", max_results=2)

    assert response.query == "agents"
    assert [result.title for result in response.results] == ["First result", "Second result"]
    assert [result.rank.position for result in response.results] == [1, 2]
    assert [result.rank.provider_position for result in response.results] == [1, 2]
    assert response.metadata.provider == "serper"
    assert response.meta.attempts == 1
    assert response.meta.retries == 0
    assert captured_request["headers"]["x-api-key"] == "serper-test-key"
    assert '"q":"agents"' in str(captured_request["json"])
    assert '"num":2' in str(captured_request["json"])


def test_serper_client_retries_429_and_recovers() -> None:
    attempts = {"count": 0}

    def handler(_request):
        attempts["count"] += 1
        if attempts["count"] == 1:
            return _json_response(429, {"message": "rate limited"})
        return _json_response(
            200,
            {
                "organic": [
                    {
                        "title": "Recovered result",
                        "link": "https://example.com/recovered",
                        "snippet": "Recovered snippet",
                        "position": 1,
                    }
                ]
            },
        )

    client = SerperClient(
        api_key="serper-test-key",
        http_client=_mock_http_client(handler),
    )

    response = client.search(query="agents", max_results=1)

    assert attempts["count"] == 2
    assert response.meta.attempts == 2
    assert response.meta.retries == 1
    assert response.results[0].title == "Recovered result"


def test_serper_client_retries_500_and_surfaces_terminal_error() -> None:
    attempts = {"count": 0}

    def handler(_request):
        attempts["count"] += 1
        return _json_response(500, {"message": "upstream failure"})

    client = SerperClient(
        api_key="serper-test-key",
        http_client=_mock_http_client(handler),
    )

    with pytest.raises(RetryableSerperError) as exc_info:
        client.search(query="agents", max_results=1)

    assert attempts["count"] == 3
    assert exc_info.value.kind == "provider_unavailable"
    assert exc_info.value.status_code == 500
    assert exc_info.value.attempt_number == 3
    assert exc_info.value.retryable is True


def test_serper_client_fails_fast_on_non_retryable_400() -> None:
    attempts = {"count": 0}

    def handler(_request):
        attempts["count"] += 1
        return _json_response(400, {"message": "bad request"})

    client = SerperClient(
        api_key="serper-test-key",
        http_client=_mock_http_client(handler),
    )

    with pytest.raises(NonRetryableSerperError) as exc_info:
        client.search(query="agents", max_results=1)

    assert attempts["count"] == 1
    assert exc_info.value.kind == "invalid_request"
    assert exc_info.value.status_code == 400
    assert exc_info.value.attempt_number == 1
    assert exc_info.value.retryable is False


def _mock_http_client(handler) -> object:
    transport = httpx.MockTransport(handler)
    return httpx.Client(transport=transport)


def _json_response(status_code: int, payload: dict[str, object]) -> object:
    return httpx.Response(status_code=status_code, json=payload)
