from __future__ import annotations

from backend.api.schemas.chat.message import ChatMessage
from backend.agent.deep_research.coordinator import DeepResearchCoordinator


def test_deep_research_coordinator_requests_clarification_on_first_turn() -> None:
    coordinator = DeepResearchCoordinator()

    answer = coordinator.respond(
        thread_id="thread-1",
        history=[],
        latest_user_message="Research the vendor landscape",
    )

    assert answer.text == "Need one more detail before I decompose the research."


def test_deep_research_coordinator_uses_history_to_change_later_turn_behavior() -> None:
    coordinator = DeepResearchCoordinator()
    history = [
        ChatMessage(
            message_id="user-1",
            thread_id="thread-1",
            role="user",
            content="Research the vendor landscape",
            created_at="2026-03-25T00:00:00Z",
        ),
        ChatMessage(
            message_id="assistant-1",
            thread_id="thread-1",
            role="assistant",
            content="Need one more detail before I decompose the research.",
            created_at="2026-03-25T00:00:01Z",
        ),
    ]

    answer = coordinator.respond(
        thread_id="thread-1",
        history=history,
        latest_user_message="Focus on enterprise browser automation vendors in 2025.",
    )

    assert "Research plan:" in answer.text
    assert "enterprise browser automation vendors in 2025" in answer.text
