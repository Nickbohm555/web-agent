from __future__ import annotations

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from backend.api.schemas.chat import (
    ChatErrorResponse,
    CreateChatThreadRequest,
    CreateChatThreadResponse,
    GetChatThreadResponse,
    PostChatMessageRequest,
    PostChatMessageResponse,
)
from backend.api.schemas.chat.errors import ChatErrorDetail
from backend.api.services.chat_threads import ChatThreadNotFoundError

router = APIRouter()


@router.post(
    "/api/chat/threads",
    status_code=201,
    response_model=CreateChatThreadResponse,
)
async def create_chat_thread(
    payload: CreateChatThreadRequest,
    request: Request,
) -> CreateChatThreadResponse:
    service = request.app.state.chat_thread_service
    return CreateChatThreadResponse(thread=service.create_thread(mode=payload.mode))


@router.get(
    "/api/chat/threads/{thread_id}",
    response_model=GetChatThreadResponse,
    responses={404: {"model": ChatErrorResponse}},
)
async def get_chat_thread(
    thread_id: str,
    request: Request,
) -> GetChatThreadResponse | JSONResponse:
    service = request.app.state.chat_thread_service
    try:
        return service.get_thread(thread_id)
    except ChatThreadNotFoundError:
        return _not_found_response()


@router.post(
    "/api/chat/threads/{thread_id}/messages",
    response_model=PostChatMessageResponse,
    responses={400: {"model": ChatErrorResponse}, 404: {"model": ChatErrorResponse}},
)
async def post_chat_message(
    thread_id: str,
    payload: PostChatMessageRequest,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> PostChatMessageResponse | JSONResponse:
    if idempotency_key is None or not idempotency_key.strip():
        return JSONResponse(
            status_code=400,
            content=ChatErrorResponse(
                error=ChatErrorDetail(
                    code="IDEMPOTENCY_KEY_REQUIRED",
                    message="Idempotency-Key header is required.",
                )
            ).model_dump(),
        )

    service = request.app.state.chat_thread_service
    try:
        return service.post_message(
            thread_id,
            content=payload.content,
            idempotency_key=idempotency_key.strip(),
        )
    except ChatThreadNotFoundError:
        return _not_found_response()


def _not_found_response() -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content=ChatErrorResponse(
            error=ChatErrorDetail(
                code="THREAD_NOT_FOUND",
                message="Chat thread was not found.",
            )
        ).model_dump(),
    )
