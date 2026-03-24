from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class _FakeRuntimeContext:
    def __init__(self, run_id: str = "run-test-123", thread_id: str = "thread-test-123") -> None:
        self.run_id = run_id
        self.thread_id = thread_id


class _FakeToolRuntime:
    def __init__(self, run_id: str = "run-test-123", thread_id: str = "thread-test-123") -> None:
        self.context = _FakeRuntimeContext(run_id=run_id, thread_id=thread_id)
        self.state = {}
        self.store = object()


@pytest.fixture
def fake_tool_runtime() -> _FakeToolRuntime:
    return _FakeToolRuntime()


@pytest.fixture(autouse=True)
def deep_research_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "DEEP_RESEARCH_DATABASE_URL",
        "postgresql://postgres:postgres@postgres:5432/web_agent",
    )
