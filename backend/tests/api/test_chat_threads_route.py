from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.agent.schemas import AgentRunResult
from backend.main import create_app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test-key")
    monkeypatch.setenv("SERPER_API_KEY", "serper-test-key")

    with TestClient(create_app()) as test_client:
        yield test_client


def test_create_thread_returns_typed_thread_metadata(client: TestClient) -> None:
    response = client.post("/api/chat/threads", json={"mode": "agentic"})

    assert response.status_code == 201
    assert response.json()["thread"]["mode"] == "agentic"


def test_get_thread_returns_ordered_transcript(client: TestClient) -> None:
    thread = client.post("/api/chat/threads", json={"mode": "deep_research"}).json()["thread"]

    response = client.get(f"/api/chat/threads/{thread['thread_id']}")

    assert response.status_code == 200
    assert response.json()["messages"] == []


def test_post_message_returns_typed_not_found_error_for_unknown_thread(client: TestClient) -> None:
    response = client.post(
        "/api/chat/threads/thread-missing/messages",
        json={"content": "Find sources"},
        headers={"Idempotency-Key": "msg-1"},
    )

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "THREAD_NOT_FOUND",
            "message": "Chat thread was not found.",
        }
    }


def test_post_message_returns_user_and_assistant_messages_for_agentic_threads(
    client: TestClient,
) -> None:
    client.app.state.agentic_chat_runtime._agent_runner = (  # noqa: SLF001
        lambda prompt, mode="agentic", **_: AgentRunResult(
            run_id="run-agentic-1",
            status="completed",
            final_answer="Thread answer",
            sources=[],
            tool_call_count=1,
            elapsed_ms=10,
        )
    )
    thread = client.post("/api/chat/threads", json={"mode": "agentic"}).json()["thread"]

    response = client.post(
        f"/api/chat/threads/{thread['thread_id']}/messages",
        json={"content": "Find sources"},
        headers={"Idempotency-Key": "msg-1"},
    )

    assert response.status_code == 200
    assert response.json()["user_message"]["role"] == "user"
    assert response.json()["assistant_message"]["role"] == "assistant"
