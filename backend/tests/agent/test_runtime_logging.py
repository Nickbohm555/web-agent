from __future__ import annotations

import logging

from backend.agent.runtime_logging import (
    log_agent_run_completed,
    log_agent_run_failed,
)
from backend.agent.schemas import AgentRunResult


def test_log_agent_run_completed_emits_summary_and_zero_source_warning(
    caplog,
) -> None:
    result = AgentRunResult.model_validate(
        {
            "run_id": "run-123",
            "status": "completed",
            "final_answer": {"text": "Summary without evidence."},
            "sources": [],
            "tool_call_count": 2,
            "elapsed_ms": 900,
        }
    )

    with caplog.at_level(logging.INFO, logger="backend.agent.runtime"):
        log_agent_run_completed(
            result=result,
            mode="agentic",
            prompt="summarize a blocked page",
        )

    assert "agent_run_completed" in caplog.text
    assert '"run_id": "run-123"' in caplog.text
    assert '"tool_call_count": 2' in caplog.text
    assert '"source_count": 0' in caplog.text
    assert "agent_run_completed_without_sources" in caplog.text


def test_log_agent_run_failed_emits_failure_summary(caplog) -> None:
    result = AgentRunResult.model_validate(
        {
            "run_id": "run-456",
            "status": "failed",
            "tool_call_count": 0,
            "elapsed_ms": 1200,
            "error": {
                "category": "tool_failure",
                "message": "agent tool invocation failed",
                "retryable": False,
            },
        }
    )

    with caplog.at_level(logging.INFO, logger="backend.agent.runtime"):
        log_agent_run_failed(
            result=result,
            mode="agentic",
            prompt="open the blocked page",
        )

    assert "agent_run_failed" in caplog.text
    assert '"run_id": "run-456"' in caplog.text
    assert '"category": "tool_failure"' in caplog.text
