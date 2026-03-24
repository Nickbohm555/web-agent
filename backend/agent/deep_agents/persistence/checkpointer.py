from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from backend.app.config import Settings, get_settings


def _resolve_settings(settings: Settings | None = None) -> Settings:
    return settings or get_settings()


@asynccontextmanager
async def create_deep_research_checkpointer(
    *,
    settings: Settings | None = None,
) -> AsyncIterator[AsyncPostgresSaver]:
    resolved_settings = _resolve_settings(settings)
    async with AsyncPostgresSaver.from_conn_string(
        resolved_settings.DEEP_RESEARCH_DATABASE_URL
    ) as saver:
        await saver.setup()
        yield saver
