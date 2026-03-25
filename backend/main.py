from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from backend.agent.agentic_chat_runtime import AgenticChatRuntime
from backend.agent.chat_history.idempotency import InMemoryChatIdempotencyStore
from backend.agent.chat_history.store import InMemoryChatTranscriptStore
from backend.agent.deep_research import DeepResearchCoordinator
from backend.agent.deep_research_chat_runtime import DeepResearchChatRuntime
from backend.agent.runtime import run_agent_once
from backend.api.routes.agent_run import router as agent_run_router
from backend.api.routes.chat_threads import router as chat_threads_router
from backend.api.services.chat_threads import ChatThreadService
from backend.app.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.settings = get_settings()
    app.state.chat_transcript_store = InMemoryChatTranscriptStore()
    app.state.chat_idempotency_store = InMemoryChatIdempotencyStore()
    app.state.agentic_chat_runtime = AgenticChatRuntime(
        transcript_store=app.state.chat_transcript_store,
        agent_runner=run_agent_once,
        idempotency_store=app.state.chat_idempotency_store,
    )
    app.state.deep_research_chat_runtime = DeepResearchChatRuntime(
        transcript_store=app.state.chat_transcript_store,
        coordinator=DeepResearchCoordinator(),
        idempotency_store=app.state.chat_idempotency_store,
    )
    app.state.chat_thread_service = ChatThreadService(
        transcript_store=app.state.chat_transcript_store,
        agentic_runtime=app.state.agentic_chat_runtime,
        deep_research_runtime=app.state.deep_research_chat_runtime,
    )
    yield


def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)
    app.include_router(agent_run_router)
    app.include_router(chat_threads_router)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
