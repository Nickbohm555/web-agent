from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.agent.types import AgentRunError, AgentRunMode, AgentRunResult, AgentRunRetrievalPolicy
from backend.api.contracts import AgentRunRequest, AgentRunSuccessResponse
from backend.api.errors import map_runtime_failure
from backend.app.config import get_settings
from backend.main import create_app

RUN_ROUTE_PATH = "/api/agent/run"


class StubRuntimeRunner:
    def __init__(self, result: AgentRunResult) -> None:
        self.result = result
        self.calls: list[tuple[str, AgentRunMode, AgentRunRetrievalPolicy]] = []

    def __call__(
        self,
        prompt: str,
        mode: AgentRunMode,
        retrieval_policy: AgentRunRetrievalPolicy,
    ) -> AgentRunResult:
        self.calls.append((prompt, mode, retrieval_policy))
        return self.result


@pytest.fixture(autouse=True)
def clear_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test-key")
    monkeypatch.setenv("SERPER_API_KEY", "serper-test-key")

    with TestClient(create_app()) as test_client:
        yield test_client


def test_run_request_contract_rejects_blank_prompt() -> None:
    with pytest.raises(ValidationError, match="prompt must not be empty"):
        AgentRunRequest(prompt="   ", mode="agentic")


def test_run_request_contract_forbids_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        AgentRunRequest(prompt="find one source", mode="quick", extra_field=True)


def test_run_request_contract_rejects_unknown_mode() -> None:
    with pytest.raises(ValidationError, match="Input should be 'quick', 'agentic' or 'deep_research'"):
        AgentRunRequest(prompt="find one source", mode="turbo")


def test_run_request_contract_accepts_normalized_retrieval_policy() -> None:
    payload = AgentRunRequest(
        prompt="find one source",
        mode="quick",
        retrievalPolicy={
            "search": {
                "freshness": "week",
                "include_domains": ["example.com"],
            },
            "fetch": {
                "max_age_ms": 60_000,
                "fresh": True,
            },
        },
    )

    assert payload.retrieval_policy.model_dump() == {
        "search": {
            "country": "US",
            "language": "en",
            "freshness": "week",
            "include_domains": ["example.com"],
            "exclude_domains": [],
        },
        "fetch": {
            "max_age_ms": 60_000,
            "fresh": True,
        },
    }


def test_run_success_contract_normalizes_required_response_fields() -> None:
    result = AgentRunResult(
        run_id="run-123",
        status="completed",
        final_answer="One source summary.",
        sources=[
            {
                "title": "Primary source",
                "url": "https://example.com/source",
                "snippet": "Key evidence.",
            }
        ],
        tool_call_count=2,
        elapsed_ms=81,
    )

    payload = AgentRunSuccessResponse.from_run_result(result)

    assert payload.model_dump(mode="json") == {
        "run_id": "run-123",
        "status": "completed",
        "final_answer": "One source summary.",
        "sources": [
            {
                "title": "Primary source",
                "url": "https://example.com/source",
                "snippet": "Key evidence.",
            }
        ],
        "tool_call_count": 2,
        "elapsed_ms": 81,
        "metadata": {
            "tool_call_count": 2,
            "elapsed_ms": 81,
        },
    }


@pytest.mark.parametrize(
    ("category", "retryable", "expected_status", "expected_code"),
    [
        ("invalid_prompt", False, 400, "invalid_prompt"),
        ("loop_limit", False, 422, "loop_limit_exceeded"),
        ("tool_failure", False, 502, "tool_execution_failed"),
        ("provider_failure", True, 503, "provider_request_failed"),
        ("timeout", True, 504, "agent_timeout"),
        ("internal_error", False, 500, "internal_runtime_error"),
    ],
)
def test_runtime_error_mapping_is_explicit_and_stable(
    category: str,
    retryable: bool,
    expected_status: int,
    expected_code: str,
) -> None:
    result = AgentRunResult(
        run_id="run-123",
        status="failed",
        tool_call_count=0,
        elapsed_ms=25,
        error=AgentRunError(
            category=category,
            message=f"{category} happened",
            retryable=retryable,
        ),
    )

    mapped_error = map_runtime_failure(result)

    assert mapped_error.status_code == expected_status
    assert mapped_error.payload.model_dump() == {
        "error": {
            "code": expected_code,
            "message": f"{category} happened",
            "retryable": retryable,
        }
    }


def test_run_route_rejects_blank_prompt_payload(client: TestClient) -> None:
    response = post_run(client, prompt="   ", mode="agentic")

    assert response.status_code == 422
    assert response.json()["detail"][0]["msg"] == "Value error, prompt must not be empty"


def test_run_route_rejects_unknown_request_fields(client: TestClient) -> None:
    response = client.post(
        RUN_ROUTE_PATH,
        json={"prompt": "find one source", "mode": "quick", "unexpected": True},
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["msg"] == "Extra inputs are not permitted"


def test_run_route_rejects_unknown_modes(client: TestClient) -> None:
    response = post_run(client, prompt="find one source", mode="turbo")

    assert response.status_code == 422
    assert "Input should be 'quick', 'agentic' or 'deep_research'" in response.json()["detail"][0]["msg"]


def test_run_route_returns_stable_success_envelope(client: TestClient) -> None:
    runner = StubRuntimeRunner(
        AgentRunResult(
            run_id="run-success",
            status="completed",
            final_answer="One source summary.",
            sources=[
                {
                    "title": "Primary source",
                    "url": "https://example.com/source",
                    "snippet": "Key evidence.",
                }
            ],
            tool_call_count=2,
            elapsed_ms=81,
        )
    )
    client.app.state.run_agent_once = runner

    response = post_run(client, prompt="  find one source  ", mode="quick")

    assert response.status_code == 200
    assert response.json() == {
        "run_id": "run-success",
        "status": "completed",
        "final_answer": "One source summary.",
        "sources": [
            {
                "title": "Primary source",
                "url": "https://example.com/source",
                "snippet": "Key evidence.",
            }
        ],
        "tool_call_count": 2,
        "elapsed_ms": 81,
        "metadata": {
            "tool_call_count": 2,
            "elapsed_ms": 81,
        },
    }
    assert response.headers["x-run-route"] == "legacy-compat"
    assert response.headers["x-run-execution-surface"] == "sync"
    assert runner.calls == [("find one source", "quick", AgentRunRetrievalPolicy())]


@pytest.mark.parametrize(
    ("category", "retryable", "expected_status", "expected_payload"),
    [
        (
            "loop_limit",
            False,
            422,
            {
                "error": {
                    "code": "loop_limit_exceeded",
                    "message": "agent exceeded bounded execution limit",
                    "retryable": False,
                }
            },
        ),
        (
            "tool_failure",
            False,
            502,
            {
                "error": {
                    "code": "tool_execution_failed",
                    "message": "agent tool invocation failed",
                    "retryable": False,
                }
            },
        ),
        (
            "provider_failure",
            True,
            503,
            {
                "error": {
                    "code": "provider_request_failed",
                    "message": "agent provider request failed",
                    "retryable": True,
                }
            },
        ),
    ],
)
def test_run_route_maps_runtime_failures_to_explicit_api_errors(
    client: TestClient,
    category: str,
    retryable: bool,
    expected_status: int,
    expected_payload: dict[str, dict[str, str | bool]],
) -> None:
    runner = StubRuntimeRunner(
        AgentRunResult(
            run_id="run-failure",
            status="failed",
            tool_call_count=1,
            elapsed_ms=54,
            error=AgentRunError(
                category=category,
                message=expected_payload["error"]["message"],
                retryable=retryable,
            ),
        )
    )
    client.app.state.run_agent_once = runner

    response = post_run(client, prompt="find one source", mode="deep_research")

    assert response.status_code == expected_status
    assert response.json() == expected_payload
    assert response.headers["x-run-route"] == "legacy-compat"
    assert response.headers["x-run-execution-surface"] == "sync"
    assert runner.calls == [("find one source", "deep_research", AgentRunRetrievalPolicy())]


def test_run_route_forwards_retrieval_policy_to_runtime(client: TestClient) -> None:
    runner = StubRuntimeRunner(
        AgentRunResult(
            run_id="run-success",
            status="completed",
            final_answer="Scoped answer.",
            tool_call_count=1,
            elapsed_ms=12,
        )
    )
    client.app.state.run_agent_once = runner

    response = client.post(
        RUN_ROUTE_PATH,
        json={
            "prompt": "find one source",
            "mode": "quick",
            "retrievalPolicy": {
                "search": {
                    "freshness": "week",
                    "include_domains": ["example.com"],
                    "exclude_domains": ["blocked.com"],
                },
                "fetch": {
                    "max_age_ms": 60_000,
                    "fresh": True,
                },
            },
        },
    )

    assert response.status_code == 200
    assert runner.calls == [
        (
            "find one source",
            "quick",
            AgentRunRetrievalPolicy.model_validate(
                {
                    "search": {
                        "freshness": "week",
                        "include_domains": ["example.com"],
                        "exclude_domains": ["blocked.com"],
                    },
                    "fetch": {
                        "max_age_ms": 60_000,
                        "fresh": True,
                    },
                }
            ),
        )
    ]


def post_run(client: TestClient, *, prompt: str, mode: str):
    return client.post(RUN_ROUTE_PATH, json={"prompt": prompt, "mode": mode})
