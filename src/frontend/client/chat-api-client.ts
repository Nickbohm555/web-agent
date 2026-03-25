import {
  parseChatError,
  parseCreateChatThreadResponse,
  parseGetChatThreadResponse,
  parsePostChatMessageResponse,
  type CreateChatThreadRequest,
  type CreateChatThreadResponse,
  type GetChatThreadResponse,
  type PostChatMessageRequest,
  type PostChatMessageResponse,
} from "../contracts/chat.js";

export type ChatApiResult<T> =
  | { ok: true; data: T }
  | { ok: false; message: string };

export async function createChatThread(
  request: CreateChatThreadRequest,
): Promise<ChatApiResult<CreateChatThreadResponse>> {
  try {
    const response = await fetch("/api/chat/threads", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(request),
    });
    const payload = await response.json();
    if (!response.ok) {
      return { ok: false, message: parseChatError(payload).message };
    }
    return { ok: true, data: parseCreateChatThreadResponse(payload) };
  } catch (error: unknown) {
    return { ok: false, message: error instanceof Error ? error.message : "Failed to create chat thread." };
  }
}

export async function getChatThread(threadId: string): Promise<ChatApiResult<GetChatThreadResponse>> {
  try {
    const response = await fetch(`/api/chat/threads/${encodeURIComponent(threadId)}`);
    const payload = await response.json();
    if (!response.ok) {
      return { ok: false, message: parseChatError(payload).message };
    }
    return { ok: true, data: parseGetChatThreadResponse(payload) };
  } catch (error: unknown) {
    return { ok: false, message: error instanceof Error ? error.message : "Failed to load chat thread." };
  }
}

export async function postChatMessage(
  threadId: string,
  request: PostChatMessageRequest,
  idempotencyKey: string,
): Promise<ChatApiResult<PostChatMessageResponse>> {
  try {
    const response = await fetch(`/api/chat/threads/${encodeURIComponent(threadId)}/messages`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "Idempotency-Key": idempotencyKey,
      },
      body: JSON.stringify(request),
    });
    const payload = await response.json();
    if (!response.ok) {
      return { ok: false, message: parseChatError(payload).message };
    }
    return { ok: true, data: parsePostChatMessageResponse(payload) };
  } catch (error: unknown) {
    return { ok: false, message: error instanceof Error ? error.message : "Failed to post chat message." };
  }
}
