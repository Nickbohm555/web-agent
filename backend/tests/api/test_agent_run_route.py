from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.agent.schemas import AgentRunError, AgentRunMode, AgentRunResult
from backend.api.errors import map_runtime_failure
from backend.api.schemas import (
    AgentRunRequest,
    AgentRunSuccessResponse,
)
from backend.api.services import agent_run as agent_run_service
from backend.app.config import get_settings
from backend.main import create_app

RUN_ROUTE_PATH = "/api/agent/run"


class StubRuntimeRunner:
    def __init__(self, result: AgentRunResult) -> None:
        self.result = result
        self.calls: list[tuple[str, AgentRunMode, str | None]] = []

    def __call__(
        self,
        prompt: str,
        mode: AgentRunMode,
        thread_id: str | None = None,
    ) -> AgentRunResult:
        self.calls.append((prompt, mode, thread_id))
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
    with pytest.raises(ValidationError, match="Input should be 'quick' or 'agentic'"):
        AgentRunRequest(prompt="find one source", mode="turbo")


def test_run_request_contract_forbids_legacy_retrieval_policy_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        AgentRunRequest(
            prompt="find one source",
            mode="quick",
            retrievalPolicy={"search": {"freshness": "week"}},
        )


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
        "final_answer": {
            "text": "One source summary.",
            "citations": [],
            "basis": [],
        },
        "sources": [
            {
                "source_id": "https-example-com-source",
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


def test_run_success_contract_preserves_structured_citations() -> None:
    result = AgentRunResult(
        run_id="run-456",
        status="completed",
        final_answer={
            "text": "Alpha leads Beta.",
            "citations": [
                {
                    "source_id": "alpha-report",
                    "title": "Alpha report",
                    "url": "https://example.com/alpha",
                    "start_index": 0,
                    "end_index": 5,
                }
            ],
        },
        sources=[
            {
                "source_id": "alpha-report",
                "title": "Alpha report",
                "url": "https://example.com/alpha",
                "snippet": "Alpha evidence.",
            }
        ],
        tool_call_count=1,
        elapsed_ms=33,
    )

    payload = AgentRunSuccessResponse.from_run_result(result)

    assert payload.model_dump(mode="json") == {
        "run_id": "run-456",
        "status": "completed",
        "final_answer": {
            "text": "Alpha leads Beta.",
            "citations": [
                {
                    "source_id": "alpha-report",
                    "title": "Alpha report",
                    "url": "https://example.com/alpha",
                    "start_index": 0,
                    "end_index": 5,
                }
            ],
            "basis": [],
        },
        "sources": [
            {
                "source_id": "alpha-report",
                "title": "Alpha report",
                "url": "https://example.com/alpha",
                "snippet": "Alpha evidence.",
            }
        ],
        "tool_call_count": 1,
        "elapsed_ms": 33,
        "metadata": {
            "tool_call_count": 1,
            "elapsed_ms": 33,
        },
    }


def test_run_success_contract_preserves_granular_basis_items() -> None:
    result = AgentRunResult(
        run_id="run-789",
        status="completed",
        final_answer={
            "text": "Alpha leads. Beta follows.",
            "citations": [
                {
                    "source_id": "alpha-report",
                    "title": "Alpha report",
                    "url": "https://example.com/alpha",
                    "start_index": 0,
                    "end_index": 12,
                }
            ],
            "basis": [
                {
                    "kind": "claim",
                    "text": "Alpha leads.",
                    "citations": [
                        {
                            "source_id": "alpha-report",
                            "title": "Alpha report",
                            "url": "https://example.com/alpha",
                            "start_index": 0,
                            "end_index": 12,
                        }
                    ],
                }
            ],
        },
        sources=[
            {
                "source_id": "alpha-report",
                "title": "Alpha report",
                "url": "https://example.com/alpha",
                "snippet": "Alpha evidence.",
            }
        ],
        tool_call_count=1,
        elapsed_ms=34,
    )

    payload = AgentRunSuccessResponse.from_run_result(result)

    assert payload.model_dump(mode="json")["final_answer"]["basis"] == [
        {
            "kind": "claim",
            "text": "Alpha leads.",
            "citations": [
                {
                    "source_id": "alpha-report",
                    "title": "Alpha report",
                    "url": "https://example.com/alpha",
                    "start_index": 0,
                    "end_index": 12,
                }
            ],
        }
    ]


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
    assert "Input should be 'quick' or 'agentic'" in response.json()["detail"][0]["msg"]


def test_run_route_returns_stable_success_envelope_for_quick_mode(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mode: AgentRunMode = "quick"
    runner = StubRuntimeRunner(
        AgentRunResult(
            run_id=f"run-{mode}-success",
            status="completed",
            final_answer=f"{mode} source summary.",
            sources=[
                {
                    "title": f"{mode} source",
                    "url": f"https://example.com/{mode}",
                    "snippet": f"Evidence for {mode}.",
                }
            ],
            tool_call_count=2,
            elapsed_ms=81,
        )
    )
    monkeypatch.setattr(agent_run_service, "run_agent_once", runner)

    response = post_run(client, prompt="  find one source  ", mode=mode)

    assert response.status_code == 200
    assert response.json() == {
        "run_id": f"run-{mode}-success",
        "status": "completed",
        "final_answer": {
            "text": f"{mode} source summary.",
            "citations": [],
            "basis": [],
        },
        "sources": [
            {
                "source_id": f"https-example-com-{mode.replace('_', '-')}",
                "title": f"{mode} source",
                "url": f"https://example.com/{mode}",
                "snippet": f"Evidence for {mode}.",
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
    assert runner.calls == [("find one source", mode, None)]


def test_run_route_returns_stable_success_envelope_for_agentic_mode_with_thread_id(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = StubRuntimeRunner(
        AgentRunResult(
            run_id="run-agentic-thread",
            status="completed",
            final_answer="Threaded answer.",
            sources=[],
            tool_call_count=1,
            elapsed_ms=44,
        )
    )
    monkeypatch.setattr(agent_run_service, "run_agent_once", runner)

    response = client.post(
        RUN_ROUTE_PATH,
        json={
            "prompt": "continue the previous conversation",
            "mode": "agentic",
            "thread_id": "thread-agentic-123",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "run_id": "run-agentic-thread",
        "status": "completed",
        "final_answer": {
            "text": "Threaded answer.",
            "citations": [],
            "basis": [],
        },
        "sources": [],
        "tool_call_count": 1,
        "elapsed_ms": 44,
        "metadata": {
            "tool_call_count": 1,
            "elapsed_ms": 44,
        },
    }
    assert runner.calls == [("continue the previous conversation", "agentic", "thread-agentic-123")]
    assert response.headers["x-run-route"] == "legacy-compat"
    assert response.headers["x-run-execution-surface"] == "sync"


def test_agent_run_route_rejects_deep_research_mode(
    client: TestClient,
) -> None:
    response = post_run(client, prompt="Find sources", mode="deep_research")

    assert response.status_code == 422
    assert "Input should be 'quick' or 'agentic'" in response.json()["detail"][0]["msg"]


@pytest.mark.parametrize(
    ("mode", "category", "retryable", "expected_status", "expected_payload"),
    [
        (
            "quick",
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
    ],
)
def test_run_route_maps_runtime_failures_to_explicit_api_errors(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    mode: AgentRunMode,
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
    monkeypatch.setattr(agent_run_service, "run_agent_once", runner)

    response = post_run(client, prompt="find one source", mode=mode)

    assert response.status_code == expected_status
    assert response.json() == expected_payload
    assert response.headers["x-run-route"] == "legacy-compat"
    assert response.headers["x-run-execution-surface"] == "sync"
    assert runner.calls == [("find one source", mode, None)]


def post_run(client: TestClient, *, prompt: str, mode: str):
    return client.post(RUN_ROUTE_PATH, json={"prompt": prompt, "mode": mode})


def test_run_request_contract_accepts_optional_thread_id() -> None:
    payload = AgentRunRequest(
        prompt="continue the prior thread",
        mode="agentic",
        thread_id="thread-agentic-123",
    )

    assert payload.model_dump() == {
        "prompt": "continue the prior thread",
        "mode": "agentic",
        "thread_id": "thread-agentic-123",
    }
