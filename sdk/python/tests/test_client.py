from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from web_agent_sdk import WebAgentClient
from web_agent_sdk.errors import WebAgentSdkError


@dataclass
class RecordedCall:
    kwargs: dict


class FakeResponsesClient:
    def __init__(self, response: object) -> None:
        self.response = response
        self.calls: list[RecordedCall] = []

    def create(self, **kwargs):
        self.calls.append(RecordedCall(kwargs=kwargs))
        return self.response


class FakeOpenAIClient:
    def __init__(self, response: object) -> None:
        self.responses = FakeResponsesClient(response)


def make_response(*, text: str, annotations: list[dict] | None = None) -> object:
    return SimpleNamespace(
        output_text=text,
        output=[
            SimpleNamespace(
                content=[
                    SimpleNamespace(
                        annotations=annotations or [],
                    )
                ]
            )
        ],
    )


def test_quick_search_uses_openai_responses_api_with_model_and_query() -> None:
    openai_client = FakeOpenAIClient(
        make_response(
            text="Pricing starts at $20.",
            annotations=[
                {
                    "title": "Pricing",
                    "url": "https://example.com/pricing",
                }
            ],
        )
    )
    client = WebAgentClient(
        api_key="openai-key",
        model="gpt-5.4-mini",
        openai_client=openai_client,
    )

    response = client.quick_search("Find pricing")

    assert response.query == "Find pricing"
    assert response.answer == "Pricing starts at $20."
    assert response.model == "gpt-5.4-mini"
    assert response.sources[0].title == "Pricing"
    assert str(response.sources[0].url) == "https://example.com/pricing"
    assert openai_client.responses.calls[0].kwargs == {
        "model": "gpt-5.4-mini",
        "input": "Find pricing",
        "instructions": "Answer the query quickly using web search. Keep the response concise and factual.",
        "tools": [{"type": "web_search"}],
        "store": False,
    }


def test_agentic_search_uses_openai_responses_api_without_memory() -> None:
    openai_client = FakeOpenAIClient(
        make_response(
            text="Company overview with supporting evidence.",
            annotations=[
                {
                    "title": "Company homepage",
                    "url": "https://example.com",
                }
            ],
        )
    )
    client = WebAgentClient(
        api_key="openai-key",
        model="gpt-5.4",
        openai_client=openai_client,
    )

    response = client.agentic_search("Investigate this company")

    assert response.query == "Investigate this company"
    assert response.answer == "Company overview with supporting evidence."
    assert response.model == "gpt-5.4"
    assert response.sources[0].title == "Company homepage"
    assert openai_client.responses.calls[0].kwargs == {
        "model": "gpt-5.4",
        "input": "Investigate this company",
        "instructions": (
            "Investigate the query thoroughly using web search in a single stateless run. "
            "Synthesize a complete answer and cite the strongest sources."
        ),
        "tools": [{"type": "web_search"}],
        "store": False,
    }


def test_agentic_search_wraps_openai_errors() -> None:
    class FailingResponsesClient:
        def create(self, **kwargs):
            raise RuntimeError("upstream failed")

    openai_client = SimpleNamespace(responses=FailingResponsesClient())
    client = WebAgentClient(
        api_key="openai-key",
        model="gpt-5.4",
        openai_client=openai_client,
    )

    try:
        client.agentic_search("Investigate this company")
    except WebAgentSdkError as error:
        assert str(error) == "upstream failed"
        assert error.code == "OPENAI_REQUEST_FAILED"
        assert error.retryable is False
    else:
        raise AssertionError("Expected WebAgentSdkError")
