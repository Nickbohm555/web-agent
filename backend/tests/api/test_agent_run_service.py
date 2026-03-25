from __future__ import annotations

from fastapi.responses import JSONResponse

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


def test_execute_agent_run_request_rejects_non_quick_modes() -> None:
    response = agent_run_service.execute_agent_run_request(
        AgentRunRequest(prompt="Investigate deeply", mode="deep_research")
    )

    assert isinstance(response, JSONResponse)
    assert response.status_code == 400
    assert response.body.decode("utf-8") == (
        '{"error":{"code":"UNSUPPORTED_MODE",'
        '"message":"Use thread-based chat routes for agentic and deep research.",'
        '"retryable":false}}'
    )
