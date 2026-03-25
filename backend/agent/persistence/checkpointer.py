from __future__ import annotations

from contextlib import contextmanager
from collections.abc import Iterator

from langgraph.checkpoint.postgres import PostgresSaver

from backend.app.config import Settings, get_settings


def _resolve_settings(settings: Settings | None = None) -> Settings:
    return settings or get_settings()


@contextmanager
def create_agent_checkpointer(
    *,
    settings: Settings | None = None,
) -> Iterator[PostgresSaver]:
    resolved_settings = _resolve_settings(settings)
    with PostgresSaver.from_conn_string(
        resolved_settings.DEEP_RESEARCH_DATABASE_URL
    ) as saver:
        saver.setup()
        yield saver
