from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from backend.agent.schemas import AgentRunError
from backend.agent.schemas.deep_research import DeepResearchJob, DeepResearchStage
from backend.agent.deep_research_store import InMemoryDeepResearchStore
from backend.app.config import get_settings
from backend.main import create_app


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


def test_deep_research_status_route_returns_completed_payload(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = InMemoryDeepResearchStore()
    store.save(
        DeepResearchJob(
            job_id="run-deep-complete",
            thread_id="thread-run-deep-complete",
            prompt="Research OpenAI",
            stage=DeepResearchStage.COMPLETED,
            sub_questions=["What is OpenAI?"],
            final_answer={"text": "OpenAI is an AI research company."},
            sources=[
                {
                    "title": "OpenAI",
                    "url": "https://openai.com/about",
                    "snippet": "OpenAI is an AI research and deployment company.",
                }
            ],
        )
    )
    monkeypatch.setattr(
        "backend.api.services.agent_run.get_default_deep_research_store",
        lambda: store,
    )

    response = client.get("/api/agent/deep-research/run-deep-complete")

    assert response.status_code == 200
    assert response.json() == {
        "run_id": "run-deep-complete",
        "thread_id": "thread-run-deep-complete",
        "status": "completed",
        "final_answer": {
            "text": "OpenAI is an AI research company.",
            "citations": [],
            "basis": [],
        },
        "sources": [
            {
                "source_id": "https-openai-com-about",
                "title": "OpenAI",
                "url": "https://openai.com/about",
                "snippet": "OpenAI is an AI research and deployment company.",
            }
        ],
        "error": None,
        "sub_questions": ["What is OpenAI?"],
        "metadata": {
            "execution_surface": "background",
            "stage": "completed",
            "wave_count": 0,
        },
    }


def test_deep_research_status_route_returns_failed_payload(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = InMemoryDeepResearchStore()
    store.save(
        DeepResearchJob(
            job_id="run-deep-failed",
            thread_id="thread-run-deep-failed",
            prompt="Research OpenAI",
            stage=DeepResearchStage.FAILED,
            error=AgentRunError(
                category="internal_error",
                message="deep research failed",
                retryable=False,
            ),
        )
    )
    monkeypatch.setattr(
        "backend.api.services.agent_run.get_default_deep_research_store",
        lambda: store,
    )

    response = client.get("/api/agent/deep-research/run-deep-failed")

    assert response.status_code == 200
    assert response.json()["error"] == {
        "category": "internal_error",
        "message": "deep research failed",
        "retryable": False,
    }


def test_deep_research_status_route_returns_not_found_error(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "backend.api.services.agent_run.get_default_deep_research_store",
        InMemoryDeepResearchStore,
    )

    response = client.get("/api/agent/deep-research/run-missing")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "run_not_found",
            "message": "Unknown deep research run: run-missing",
            "retryable": False,
        }
    }
