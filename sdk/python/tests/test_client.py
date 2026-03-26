from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from web_agent_sdk import WebAgentClient, agentic_search, quick_search
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


class FakeSecret:
    def __init__(self, value: str) -> None:
        self._value = value

    def get_secret_value(self) -> str:
        return self._value


class FakeChatOpenAI:
    def __init__(self, *, model_name: str, api_key: str, response: object) -> None:
        self.model_name = model_name
        self.openai_api_key = FakeSecret(api_key)
        self._response = response

    def build_client(self) -> FakeOpenAIClient:
        return FakeOpenAIClient(self._response)


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


def test_quick_search_uses_injected_chat_model_configuration() -> None:
    chat_model = FakeChatOpenAI(
        model_name="gpt-5.4-mini",
        api_key="openai-key",
        response=make_response(
            text="Pricing starts at $20.",
            annotations=[
                {
                    "title": "Pricing",
                    "url": "https://example.com/pricing",
                }
            ],
        ),
    )
    client = WebAgentClient(
        chat_model=chat_model,
        openai_client_factory=lambda model: model.build_client(),
    )

    response = client.quick_search("Find pricing")

    assert response.query == "Find pricing"
    assert response.answer == "Pricing starts at $20."
    assert response.model == "gpt-5.4-mini"
    assert response.sources[0].title == "Pricing"
    assert str(response.sources[0].url) == "https://example.com/pricing"


def test_agentic_search_uses_stateless_openai_responses_api() -> None:
    chat_model = FakeChatOpenAI(
        model_name="gpt-5.4",
        api_key="openai-key",
        response=make_response(
            text="Company overview with supporting evidence.",
            annotations=[
                {
                    "title": "Company homepage",
                    "url": "https://example.com",
                }
            ],
        ),
    )
    openai_client = chat_model.build_client()
    client = WebAgentClient(
        chat_model=chat_model,
        openai_client_factory=lambda _: openai_client,
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


def test_top_level_helpers_accept_chat_model() -> None:
    chat_model = FakeChatOpenAI(
        model_name="gpt-5.4-nano",
        api_key="openai-key",
        response=make_response(text="Answer"),
    )

    quick = quick_search(
        "What changed?",
        chat_model=chat_model,
        openai_client_factory=lambda model: model.build_client(),
    )
    agentic = agentic_search(
        "Explain the change",
        chat_model=chat_model,
        openai_client_factory=lambda model: model.build_client(),
    )

    assert quick.model == "gpt-5.4-nano"
    assert agentic.model == "gpt-5.4-nano"


def test_missing_chat_model_configuration_raises_clear_error() -> None:
    chat_model = SimpleNamespace(model_name="", openai_api_key=FakeSecret(""))

    with pytest.raises(ValueError, match="chat_model must expose a non-empty OpenAI model name"):
        WebAgentClient(chat_model=chat_model)


def test_agentic_search_wraps_openai_errors() -> None:
    class FailingResponsesClient:
        def create(self, **kwargs):
            raise RuntimeError("upstream failed")

    chat_model = FakeChatOpenAI(
        model_name="gpt-5.4",
        api_key="openai-key",
        response=make_response(text="unused"),
    )
    openai_client = SimpleNamespace(responses=FailingResponsesClient())
    client = WebAgentClient(
        chat_model=chat_model,
        openai_client_factory=lambda _: openai_client,
    )

    with pytest.raises(WebAgentSdkError, match="upstream failed") as error_info:
        client.agentic_search("Investigate this company")

    error = error_info.value
    assert error.code == "OPENAI_REQUEST_FAILED"
    assert error.retryable is False
