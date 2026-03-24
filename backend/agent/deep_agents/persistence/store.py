from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from langgraph.store.postgres.aio import AsyncPostgresStore

from backend.app.config import Settings, get_settings


def _resolve_settings(settings: Settings | None = None) -> Settings:
    return settings or get_settings()


@asynccontextmanager
async def create_deep_research_store(
    *,
    settings: Settings | None = None,
) -> AsyncIterator[AsyncPostgresStore]:
    resolved_settings = _resolve_settings(settings)
    async with AsyncPostgresStore.from_conn_string(
        resolved_settings.DEEP_RESEARCH_DATABASE_URL
    ) as store:
        await store.setup()
        yield store
