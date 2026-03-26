from __future__ import annotations

from types import SimpleNamespace

import pytest

from web_agent_backend.responses import (
    OpenAIResponsesBackend,
    extract_chat_model_config,
)
from web_agent_sdk.errors import WebAgentSdkError


class FakeSecret:
    def __init__(self, value: str) -> None:
        self._value = value

    def get_secret_value(self) -> str:
        return self._value


class FakeResponsesClient:
    def __init__(self, response: object) -> None:
        self.response = response
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


def test_extract_chat_model_config_reads_model_name_and_secret_api_key() -> None:
    chat_model = SimpleNamespace(
        model_name="gpt-5-nano",
        openai_api_key=FakeSecret("sk-test"),
    )

    config = extract_chat_model_config(chat_model)

    assert config.model == "gpt-5-nano"
    assert config.api_key == "sk-test"


def test_extract_chat_model_config_rejects_missing_api_key() -> None:
    chat_model = SimpleNamespace(model_name="gpt-5-nano", openai_api_key=FakeSecret(""))

    with pytest.raises(ValueError, match="chat_model must expose a non-empty OpenAI api key"):
        extract_chat_model_config(chat_model)


def test_backend_wraps_invalid_response_text() -> None:
    backend = OpenAIResponsesBackend(
        model="gpt-5-nano",
        openai_client=SimpleNamespace(
            responses=FakeResponsesClient(
                SimpleNamespace(
                    output_text="",
                    output=[],
                )
            )
        ),
    )

    with pytest.raises(WebAgentSdkError, match="OpenAI response did not include output text"):
        backend.quick_search("hello")
