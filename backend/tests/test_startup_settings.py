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

    with pytest.raises(ValidationError) as exc_info:
        with TestClient(app):
            pass

    assert "OPENAI_API_KEY" in str(exc_info.value)


def test_startup_fails_when_serper_api_key_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test-key")
    monkeypatch.delenv("SERPER_API_KEY", raising=False)

    with pytest.raises(ValidationError) as exc_info:
        with TestClient(app):
            pass

    assert "SERPER_API_KEY" in str(exc_info.value)


def test_startup_ignores_agent_database_url_when_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test-key")
    monkeypatch.setenv("SERPER_API_KEY", "serper-test-key")
    monkeypatch.delenv("AGENT_DATABASE_URL", raising=False)

    with TestClient(app) as client:
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


def test_startup_succeeds_when_required_keys_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "openai-test-key")
    monkeypatch.setenv("SERPER_API_KEY", "serper-test-key")

    with TestClient(app) as client:
        response = client.get("/healthz")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        assert client.app.state.settings.OPENAI_API_KEY == "openai-test-key"
        assert client.app.state.settings.SERPER_API_KEY == "serper-test-key"
