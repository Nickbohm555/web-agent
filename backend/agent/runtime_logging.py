from __future__ import annotations

import json
import logging

from backend.agent.schemas import AgentRunMode, AgentRunResult


logger = logging.getLogger("backend.agent.runtime")


def log_agent_run_started(*, prompt: str, mode: AgentRunMode) -> None:
    logger.info(
        "agent_run_started %s",
        _serialize(
            {
                "mode": mode,
                "prompt_preview": _prompt_preview(prompt),
            }
        ),
    )


def log_agent_run_completed(
    *,
    result: AgentRunResult,
    mode: AgentRunMode,
    prompt: str,
) -> None:
    summary = {
        "run_id": result.run_id,
        "mode": mode,
        "status": result.status,
        "prompt_preview": _prompt_preview(prompt),
        "tool_call_count": result.tool_call_count,
        "source_count": len(result.sources),
        "elapsed_ms": result.elapsed_ms,
    }
    logger.info("agent_run_completed %s", _serialize(summary))

    if result.tool_call_count > 0 and not result.sources:
        logger.warning(
            "agent_run_completed_without_sources %s",
            _serialize(
                {
                    **summary,
                    "final_answer_preview": _final_answer_preview(result),
                }
            ),
        )


def log_agent_run_failed(
    *,
    result: AgentRunResult,
    mode: AgentRunMode,
    prompt: str,
) -> None:
    logger.warning(
        "agent_run_failed %s",
        _serialize(
            {
                "run_id": result.run_id,
                "mode": mode,
                "status": result.status,
                "prompt_preview": _prompt_preview(prompt),
                "tool_call_count": result.tool_call_count,
                "elapsed_ms": result.elapsed_ms,
                "category": result.error.category if result.error is not None else None,
                "message": result.error.message if result.error is not None else None,
                "retryable": result.error.retryable if result.error is not None else None,
            }
        ),
    )


def _serialize(payload: dict[str, object]) -> str:
    return json.dumps(payload, sort_keys=True, default=str)


def _prompt_preview(prompt: str, limit: int = 160) -> str:
    return " ".join(prompt.split())[:limit]


def _final_answer_preview(result: AgentRunResult, limit: int = 200) -> str:
    if result.final_answer is None:
        return ""
    return " ".join(result.final_answer.text.split())[:limit]
