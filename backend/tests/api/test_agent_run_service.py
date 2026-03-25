from __future__ import annotations

import json

from fastapi.responses import JSONResponse

from backend.agent.schemas import AgentRunResult
from backend.api.schemas import (
    AgentRunQueuedMetadata,
    AgentRunQueuedResponse,
    AgentRunRequest,
    AgentRunSuccessResponse,
)
from backend.api.services import agent_run as agent_run_service


def test_execute_agent_run_request_returns_sync_success_for_quick_mode(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        agent_run_service,
        "run_agent_once",
        lambda prompt, mode: AgentRunResult(
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


def test_execute_agent_run_request_returns_queued_response_for_deep_research(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        agent_run_service,
        "start_deep_research",
        lambda **kwargs: captured.setdefault(
            "response",
            AgentRunQueuedResponse(
                run_id="run-deep",
                status="queued",
                metadata=AgentRunQueuedMetadata(execution_surface="background"),
            ),
        ),
        raising=False,
    )
    monkeypatch.setattr(
        agent_run_service,
        "run_agent_once",
        lambda prompt, mode: AgentRunResult(
            run_id="run-should-not-complete",
            status="completed",
            final_answer={"text": "This should not run."},
            tool_call_count=1,
            elapsed_ms=10,
        ),
    )

    response = agent_run_service.execute_agent_run_request(
        AgentRunRequest(prompt="Investigate deeply", mode="deep_research")
    )

    assert isinstance(response, JSONResponse)
    assert response.status_code == 202
    assert json.loads(response.body.decode("utf-8")) == {
        "run_id": "run-deep",
        "status": "queued",
        "metadata": {"execution_surface": "background"},
    }
    assert captured["response"].run_id == "run-deep"
