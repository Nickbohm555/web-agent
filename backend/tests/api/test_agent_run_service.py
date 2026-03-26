from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.agent.schemas import AgentRunResult
from backend.api.schemas import AgentRunRequest, AgentRunSuccessResponse
from backend.api.services import agent_run as agent_run_service


def test_execute_agent_run_request_returns_sync_success_for_quick_mode(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        agent_run_service,
        "run_agent_once",
        lambda prompt, mode, thread_id=None: AgentRunResult(
            run_id="run-quick",
            status="completed",
            final_answer={"text": "Quick answer."},
            tool_call_count=1,
            elapsed_ms=10,
        ),
    )

    response = agent_run_service.execute_agent_run_request(
        AgentRunRequest(prompt="Find one source", mode="quick")
    )

    assert isinstance(response, AgentRunSuccessResponse)
    assert response.run_id == "run-quick"
    assert response.status == "completed"


def test_execute_agent_run_request_returns_sync_success_for_agentic_mode(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        agent_run_service,
        "run_agent_once",
        lambda prompt, mode, thread_id=None: AgentRunResult(
            run_id="run-agentic",
            status="completed",
            final_answer={"text": "Agentic answer."},
            tool_call_count=2,
            elapsed_ms=12,
        ),
    )

    response = agent_run_service.execute_agent_run_request(
        AgentRunRequest(prompt="Investigate this source", mode="agentic")
    )

    assert isinstance(response, AgentRunSuccessResponse)
    assert response.run_id == "run-agentic"
    assert response.status == "completed"


def test_execute_agent_run_request_request_contract_rejects_deep_research_mode() -> None:
    with pytest.raises(ValidationError, match="Input should be 'quick' or 'agentic'"):
        AgentRunRequest(prompt="Investigate deeply", mode="deep_research")
