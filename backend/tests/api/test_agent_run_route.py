from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.agent.types import AgentRunError, AgentRunResult
from backend.api.contracts import AgentRunRequest, AgentRunSuccessResponse
from backend.api.errors import map_runtime_failure
from backend.app.config import get_settings
from backend.main import create_app


class StubRuntimeRunner:
    def __init__(self, result: AgentRunResult) -> None:
        self.result = result
        self.calls: list[str] = []

    def __call__(self, prompt: str) -> AgentRunResult:
        self.calls.append(prompt)
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
        AgentRunRequest(prompt="   ")


def test_run_request_contract_forbids_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        AgentRunRequest(prompt="find one source", extra_field=True)


def test_run_success_contract_normalizes_required_response_fields() -> None:
    result = AgentRunResult(
        run_id="run-123",
        status="completed",
        final_answer="One source summary.",
        tool_call_count=2,
        elapsed_ms=81,
    )

    payload = AgentRunSuccessResponse.from_run_result(result)

    assert payload.model_dump() == {
        "run_id": "run-123",
        "status": "completed",
        "final_answer": "One source summary.",
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
    response = client.post("/api/agent/run", json={"prompt": "   "})

    assert response.status_code == 422
    assert response.json()["detail"][0]["msg"] == "Value error, prompt must not be empty"


def test_run_route_rejects_unknown_request_fields(client: TestClient) -> None:
    response = client.post(
        "/api/agent/run",
        json={"prompt": "find one source", "unexpected": True},
    )

    assert response.status_code == 422
    assert response.json()["detail"][0]["msg"] == "Extra inputs are not permitted"


def test_run_route_returns_stable_success_envelope(client: TestClient) -> None:
    runner = StubRuntimeRunner(
        AgentRunResult(
            run_id="run-success",
            status="completed",
            final_answer="One source summary.",
            tool_call_count=2,
            elapsed_ms=81,
        )
    )
    client.app.state.run_agent_once = runner

    response = client.post("/api/agent/run", json={"prompt": "  find one source  "})

    assert response.status_code == 200
    assert response.json() == {
        "run_id": "run-success",
        "status": "completed",
        "final_answer": "One source summary.",
        "tool_call_count": 2,
        "elapsed_ms": 81,
        "metadata": {
            "tool_call_count": 2,
            "elapsed_ms": 81,
        },
    }
    assert runner.calls == ["find one source"]


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

    response = client.post("/api/agent/run", json={"prompt": "find one source"})

    assert response.status_code == expected_status
    assert response.json() == expected_payload
    assert runner.calls == ["find one source"]
