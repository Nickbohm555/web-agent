import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.config import get_settings
from backend.app.main import app


@pytest.fixture(autouse=True)
def clear_settings_cache() -> None:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_startup_fails_when_openai_api_key_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("SERPER_API_KEY", "serper-test-key")
    monkeypatch.setenv(
        "AGENT_DATABASE_URL",
        "postgresql://postgres:postgres@postgres:5432/web_agent",
    )

    with pytest.raises(ValidationError) as exc_info:
        with TestClient(app):
            pass

    assert "OPENAI_API_KEY" in str(exc_info.value)


def test_startup_fails_when_serper_api_key_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "AGENT_DATABASE_URL",
        "postgresql://postgres:postgres@postgres:5432/web_agent",
    )
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test-key")
    monkeypatch.delenv("SERPER_API_KEY", raising=False)

    with pytest.raises(ValidationError) as exc_info:
        with TestClient(app):
            pass

    assert "SERPER_API_KEY" in str(exc_info.value)


def test_startup_fails_when_agent_database_url_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test-key")
    monkeypatch.setenv("SERPER_API_KEY", "serper-test-key")
    monkeypatch.delenv("AGENT_DATABASE_URL", raising=False)

    with pytest.raises(ValidationError) as exc_info:
        with TestClient(app):
            pass

    assert "AGENT_DATABASE_URL" in str(exc_info.value)


def test_startup_succeeds_when_required_keys_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "AGENT_DATABASE_URL",
        "postgresql://postgres:postgres@postgres:5432/web_agent",
    )
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test-key")
    monkeypatch.setenv("SERPER_API_KEY", "serper-test-key")

    with TestClient(app) as client:
        response = client.get("/healthz")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        assert (
            client.app.state.settings.AGENT_DATABASE_URL
            == "postgresql://postgres:postgres@postgres:5432/web_agent"
        )
        assert client.app.state.settings.OPENAI_API_KEY == "openai-test-key"
        assert client.app.state.settings.SERPER_API_KEY == "serper-test-key"
