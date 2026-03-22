import httpx
import pytest
from pydantic import ValidationError

from backend.app.schemas.tool_errors import ToolError, ToolErrorEnvelope, ToolMeta, ToolTimings
from backend.agent.schemas import AgentRunRetrievalPolicy
from backend.app.schemas.web_search import (
    SearchMetadata,
    SearchRank,
    WebSearchError,
    WebSearchInput,
    WebSearchResponse,
    WebSearchResult,
)
from backend.app.providers.serper_client import (
    NonRetryableSerperError,
    RetryableSerperError,
    SerperClient,
)
from backend.app.tools.web_search import (
    build_web_search_tool,
    build_web_search_action_record,
    run_web_search,
    web_search,
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
                rank=SearchRank(position=1, provider_position=2, rerank_score=12.5),
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
    assert response.results[0].rank.rerank_score == 12.5


def test_build_web_search_action_record_summarizes_success_payload() -> None:
    record = build_web_search_action_record(
        query="  agents  ",
        payload={
            "query": "agents",
            "results": [
                {
                    "title": "Example result",
                    "url": "https://example.com/article",
                    "snippet": "Summary text.",
                    "rank": {"position": 1, "provider_position": 1},
                }
            ],
            "metadata": {"result_count": 1, "provider": "serper"},
            "meta": {
                "operation": "web_search",
                "attempts": 1,
                "retries": 0,
                "duration_ms": 15,
                "timings": {"total_ms": 15, "provider_ms": 10},
            },
        },
    )

    assert record == {
        "action_type": "search",
        "query": "agents",
        "result_count": 1,
        "provider": "serper",
        "results_preview": [
            {
                "title": "Example result",
                "url": "https://example.com/article",
                "snippet": "Summary text.",
                "position": 1,
            }
        ],
    }


def test_build_web_search_action_record_summarizes_error_payload() -> None:
    record = build_web_search_action_record(
        query="  agents  ",
        payload={
            "error": {
                "kind": "provider_unavailable",
                "message": "Temporary upstream failure",
                "retryable": True,
                "status_code": 503,
                "attempt_number": 2,
                "operation": "web_search",
                "timings": {"total_ms": 400, "provider_ms": 380},
            },
            "meta": {
                "operation": "web_search",
                "attempts": 2,
                "retries": 1,
                "duration_ms": 400,
                "timings": {"total_ms": 400, "provider_ms": 380},
            },
        },
    )

    assert record == {
        "action_type": "search",
        "query": "agents",
        "error_kind": "provider_unavailable",
        "message": "Temporary upstream failure",
        "retryable": True,
        "attempts": 2,
        "status_code": 503,
    }


def test_build_web_search_action_record_accepts_pydantic_error_payload() -> None:
    record = build_web_search_action_record(
        query="agents",
        payload=WebSearchError(
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
        ),
    )

    assert record == {
        "action_type": "search",
        "query": "agents",
        "error_kind": "provider_unavailable",
        "message": "Temporary upstream failure",
        "retryable": True,
        "attempts": 2,
        "status_code": 503,
    }


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


def test_serper_client_builds_provider_snippet_from_extra_fields() -> None:
    client = SerperClient(
        api_key="serper-test-key",
        http_client=_mock_http_client(
            lambda _request: _json_response(
                200,
                {
                    "organic": [
                        {
                            "title": "Result with metadata",
                            "link": "https://example.com/metadata",
                            "date": "Jan 5, 2025",
                            "attributes": {
                                "Author": "Example Team",
                                "Reading time": "5 min",
                            },
                        }
                    ]
                },
            )
        ),
    )

    response = client.search(query="agents", max_results=1)

    assert response.results[0].snippet == (
        "Published: Jan 5, 2025 | Author: Example Team | Reading time: 5 min"
    )
    assert response.results[0].rank.provider_position == 1


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


def test_web_search_tool_returns_contract_valid_success_payload() -> None:
    client = SerperClient(
        api_key="serper-test-key",
        http_client=_mock_http_client(
            lambda _request: _json_response(
                200,
                {
                    "organic": [
                        {
                            "title": "Later provider result",
                            "link": "https://example.com/two",
                            "snippet": "Second snippet",
                            "position": 2,
                        },
                        {
                            "title": "Earlier provider result",
                            "link": "https://example.com/one",
                            "snippet": "First snippet",
                            "position": 1,
                        },
                    ]
                },
            )
        ),
    )

    payload = run_web_search(query=" agents ", max_results=2, client=client)
    response = WebSearchResponse.model_validate(payload)

    assert response.query == "agents"
    assert [result.title for result in response.results] == [
        "Earlier provider result",
        "Later provider result",
    ]
    assert [result.rank.position for result in response.results] == [1, 2]
    assert response.results[0].rank.rerank_score is not None
    assert response.meta.operation == "web_search"


def test_web_search_tool_reranks_results_by_query_relevance() -> None:
    client = SerperClient(
        api_key="serper-test-key",
        http_client=_mock_http_client(
            lambda _request: _json_response(
                200,
                {
                    "organic": [
                        {
                            "title": "Company blog",
                            "link": "https://example.com/blog",
                            "snippet": "General company update with no pricing details.",
                            "position": 1,
                        },
                        {
                            "title": "Widget pricing and enterprise plans",
                            "link": "https://example.com/pricing",
                            "snippet": (
                                "Overview. Widget pricing starts at $49 per seat for teams. "
                                "Annual discounts are available."
                            ),
                            "position": 2,
                        },
                    ]
                },
            )
        ),
    )

    payload = run_web_search(query="widget pricing", max_results=2, client=client)
    response = WebSearchResponse.model_validate(payload)

    assert [result.title for result in response.results] == [
        "Widget pricing and enterprise plans",
        "Company blog",
    ]
    assert response.results[0].rank.position == 1
    assert response.results[0].rank.provider_position == 2
    assert response.results[0].rank.rerank_score > response.results[1].rank.rerank_score


def test_web_search_tool_builds_tighter_query_aligned_snippets() -> None:
    client = SerperClient(
        api_key="serper-test-key",
        http_client=_mock_http_client(
            lambda _request: _json_response(
                200,
                {
                    "organic": [
                        {
                            "title": "Widget pricing",
                            "link": "https://example.com/pricing",
                            "snippet": (
                                "Welcome to the overview page. Widget pricing starts at $49 per seat for teams. "
                                "Contact sales for annual billing."
                            ),
                            "position": 1,
                        }
                    ]
                },
            )
        ),
    )

    payload = run_web_search(query="widget pricing", max_results=1, client=client)
    response = WebSearchResponse.model_validate(payload)

    assert response.results[0].snippet == (
        "Widget pricing starts at $49 per seat for teams. Contact sales for annual billing."
    )


def test_build_web_search_tool_caps_agent_requested_result_count() -> None:
    captured_max_results: int | None = None

    def search_runner(
        *,
        query: str,
        max_results: int = 5,
        freshness: str = "any",
    ) -> dict[str, object]:
        nonlocal captured_max_results
        captured_max_results = max_results
        return {
            "query": query,
            "results": [
                {
                    "title": "Example result",
                    "url": "https://example.com/article",
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
        }

    tool_instance = build_web_search_tool(max_results_cap=2, search_runner=search_runner)
    payload = tool_instance.invoke({"query": "agents", "max_results": 7})
    response = WebSearchResponse.model_validate(payload)

    assert tool_instance.name == "web_search"
    assert captured_max_results == 2
    assert response.metadata.result_count == 1


def test_web_search_tool_returns_structured_error_for_retryable_provider_failure() -> None:
    attempts = {"count": 0}

    def handler(_request):
        attempts["count"] += 1
        return _json_response(500, {"message": "upstream failure"})

    client = SerperClient(
        api_key="serper-test-key",
        http_client=_mock_http_client(handler),
    )

    payload = run_web_search(query="agents", max_results=1, client=client)
    envelope = ToolErrorEnvelope.model_validate(payload)

    assert attempts["count"] == 3
    assert envelope.error.kind == "provider_unavailable"
    assert envelope.error.retryable is True
    assert envelope.error.operation == "web_search"
    assert envelope.error.attempt_number == 3
    assert envelope.meta.attempts == 3
    assert envelope.meta.retries == 2


def test_web_search_tool_returns_structured_error_for_invalid_args() -> None:
    payload = run_web_search(query="   ", max_results=1)
    envelope = ToolErrorEnvelope.model_validate(payload)

    assert envelope.error.kind == "invalid_request"
    assert envelope.error.retryable is False
    assert envelope.error.operation == "web_search"
    assert envelope.error.attempt_number == 1
    assert envelope.meta.attempts == 1
    assert envelope.meta.retries == 0


def test_web_search_langchain_tool_is_callable() -> None:
    class StubClient:
        def search(self, *, query: str, max_results: int, freshness: str = "any") -> WebSearchResponse:
            return WebSearchResponse(
                query=query,
                results=[
                    WebSearchResult(
                        title="Result",
                        url="https://example.com/article",
                        snippet="Snippet",
                        rank=SearchRank(position=1, provider_position=1),
                    )
                ],
                metadata=SearchMetadata(result_count=1, provider="serper"),
                meta=ToolMeta(
                    operation="web_search",
                    attempts=1,
                    retries=0,
                    duration_ms=10,
                    timings=ToolTimings(total_ms=10, provider_ms=8),
                ),
            )

    original_func = web_search.func
    web_search.func = lambda query, max_results=5: run_web_search(
        query=query,
        max_results=max_results,
        client=StubClient(),
    )
    try:
        payload = web_search.invoke({"query": "agents", "max_results": 1})
    finally:
        web_search.func = original_func

    response = WebSearchResponse.model_validate(payload)
    assert response.results[0].title == "Result"
    assert web_search.name == "web_search"


def test_bounded_web_search_applies_retrieval_policy_to_query_and_results() -> None:
    captured: dict[str, object] = {}

    def runner(*, query: str, max_results: int, freshness: str = "any") -> WebSearchResponse:
        captured["query"] = query
        captured["freshness"] = freshness
        captured["max_results"] = max_results
        return WebSearchResponse(
            query=query,
            results=[
                WebSearchResult(
                    title="Allowed",
                    url="https://docs.example.com/article",
                    snippet="Snippet",
                    rank=SearchRank(position=1, provider_position=1),
                ),
                WebSearchResult(
                    title="Blocked",
                    url="https://blocked.com/article",
                    snippet="Snippet",
                    rank=SearchRank(position=2, provider_position=2),
                ),
            ],
            metadata=SearchMetadata(result_count=2, provider="serper"),
            meta=ToolMeta(
                operation="web_search",
                attempts=1,
                retries=0,
                duration_ms=10,
                timings=ToolTimings(total_ms=10, provider_ms=8),
            ),
        )

    tool = build_web_search_tool(
        max_results_cap=3,
        retrieval_policy=AgentRunRetrievalPolicy.model_validate(
            {
                "search": {
                    "freshness": "week",
                    "include_domains": ["example.com"],
                    "exclude_domains": ["blocked.com"],
                }
            }
        ),
        search_runner=runner,
    )

    payload = tool.invoke({"query": "agents", "max_results": 3})
    response = WebSearchResponse.model_validate(payload)

    assert captured == {
        "query": "agents site:example.com -site:blocked.com",
        "freshness": "week",
        "max_results": 3,
    }
    assert [result.title for result in response.results] == ["Allowed"]
    assert response.metadata.result_count == 1


def _mock_http_client(handler) -> object:
    transport = httpx.MockTransport(handler)
    return httpx.Client(transport=transport)


def _json_response(status_code: int, payload: dict[str, object]) -> object:
    return httpx.Response(status_code=status_code, json=payload)
