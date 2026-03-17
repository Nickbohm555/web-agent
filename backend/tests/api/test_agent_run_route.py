from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.agent.types import AgentRunError, AgentRunResult
from backend.api.contracts import AgentRunRequest, AgentRunSuccessResponse
from backend.api.errors import map_runtime_failure


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
