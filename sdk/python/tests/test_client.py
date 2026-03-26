from __future__ import annotations

import json

import httpx

from web_agent_sdk import WebAgentClient


def test_quick_search_posts_to_frontend_search_route() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert str(request.url) == "http://frontend.local/api/search"
        assert json.loads(request.content.decode("utf-8")) == {
            "query": "Find pricing",
            "options": {
                "maxResults": 3,
            },
        }
        return httpx.Response(
            200,
            json={
                "ok": True,
                "operation": "search",
                "durationMs": 17,
                "request": {
                    "query": "Find pricing",
                    "options": {
                        "maxResults": 3,
                        "timeoutMs": 10000,
                        "country": "us",
                        "language": "en",
                        "freshness": "any",
                        "domainScope": {
                            "includeDomains": [],
                            "excludeDomains": [],
                        },
                    },
                },
                "data": {
                    "query": "Find pricing",
                    "results": [
                        {
                            "title": "Pricing",
                            "url": "https://example.com/pricing",
                            "snippet": "Current pricing details.",
                            "rank": {
                                "position": 1,
                                "providerPosition": 1,
                            },
                        }
                    ],
                    "meta": {
                        "operation": "search",
                        "startedAt": "2026-03-25T00:00:00.000Z",
                        "completedAt": "2026-03-25T00:00:00.017Z",
                        "durationMs": 17,
                        "attempts": 1,
                        "retries": 0,
                        "cacheHit": False,
                        "timings": {
                            "providerMs": 12,
                            "mappingMs": 5,
                        },
                        "usage": {
                            "provider": {
                                "organicResults": 1,
                            }
                        },
                    },
                    "metadata": {
                        "resultCount": 1,
                    },
                },
            },
        )

    client = WebAgentClient(
        base_url="http://frontend.local",
        backend_base_url="http://backend.local",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    response = client.quick_search("Find pricing", max_results=3)

    assert response.query == "Find pricing"
    assert response.metadata.result_count == 1
    assert response.results[0].title == "Pricing"
    assert str(response.results[0].url) == "https://example.com/pricing"


def test_agentic_search_posts_to_backend_agent_run_route() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert str(request.url) == "http://backend.local/api/agent/run"
        assert json.loads(request.content.decode("utf-8")) == {
            "prompt": "Investigate this company",
            "mode": "agentic",
        }
        return httpx.Response(
            200,
            json={
                "run_id": "run-agentic-123",
                "status": "completed",
                "final_answer": {
                    "text": "Company overview.",
                    "citations": [],
                    "basis": [],
                },
                "sources": [
                    {
                        "source_id": "company-homepage",
                        "title": "Company homepage",
                        "url": "https://example.com",
                        "snippet": "Primary source.",
                    }
                ],
                "tool_call_count": 2,
                "elapsed_ms": 81,
                "metadata": {
                    "tool_call_count": 2,
                    "elapsed_ms": 81,
                },
            },
        )

    client = WebAgentClient(
        base_url="http://frontend.local",
        backend_base_url="http://backend.local",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    response = client.agentic_search("Investigate this company")

    assert response.run_id == "run-agentic-123"
    assert response.status == "completed"
    assert response.final_answer.text == "Company overview."
    assert response.sources[0].source_id == "company-homepage"


def test_agentic_search_raises_sdk_error_for_api_failure() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "error": {
                    "code": "UNSUPPORTED_MODE",
                    "message": "Use the deep research status workflow for deep_research mode.",
                    "retryable": False,
                }
            },
        )

    client = WebAgentClient(
        base_url="http://frontend.local",
        backend_base_url="http://backend.local",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    try:
        client.agentic_search("Investigate deeply")
    except Exception as error:
        assert type(error).__name__ == "WebAgentSdkError"
        assert str(error) == "Use the deep research status workflow for deep_research mode."
        assert getattr(error, "status_code") == 400
        assert getattr(error, "code") == "UNSUPPORTED_MODE"
    else:
        raise AssertionError("Expected WebAgentSdkError")
