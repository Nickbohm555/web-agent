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
