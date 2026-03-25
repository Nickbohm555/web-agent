import { randomUUID } from "node:crypto";
import { Router } from "express";

type ChatMode = "agentic" | "deep_research";

interface ChatThreadRecord {
  thread_id: string;
  mode: ChatMode;
  title: string | null;
  created_at: string;
  updated_at: string;
  messages: Array<{
    message_id: string;
    thread_id: string;
    role: "user" | "assistant";
    content: string;
    created_at: string;
    sources: [] | null;
  }>;
}

export function createChatRouter(): Router {
  const router = Router();

  router.post("/threads", (req, res) => {
    const mode = req.body?.mode;
    if (mode !== "agentic" && mode !== "deep_research") {
      res.status(400).json({
        error: {
          code: "VALIDATION_ERROR",
          message: "Chat mode must be agentic or deep_research.",
        },
      });
      return;
    }

    const thread = createThread(mode);
    getChatStore(req.app.locals.chatThreadStore).set(thread.thread_id, thread);
    res.status(201).json({ thread: summarizeThread(thread) });
  });

  router.get("/threads/:threadId", (req, res) => {
    const thread = getChatStore(req.app.locals.chatThreadStore).get(req.params.threadId);
    if (!thread) {
      res.status(404).json({
        error: {
          code: "THREAD_NOT_FOUND",
          message: "Chat thread was not found.",
        },
      });
      return;
    }

    res.status(200).json({
      thread: summarizeThread(thread),
      messages: thread.messages,
    });
  });

  router.post("/threads/:threadId/messages", (req, res) => {
    const thread = getChatStore(req.app.locals.chatThreadStore).get(req.params.threadId);
    if (!thread) {
      res.status(404).json({
        error: {
          code: "THREAD_NOT_FOUND",
          message: "Chat thread was not found.",
        },
      });
      return;
    }

    const content = typeof req.body?.content === "string" ? req.body.content.trim() : "";
    if (!content) {
      res.status(400).json({
        error: {
          code: "VALIDATION_ERROR",
          message: "content is required.",
        },
      });
      return;
    }

    const userMessage = createMessage(thread.thread_id, "user", content);
    const assistantMessage = createMessage(
      thread.thread_id,
      "assistant",
      thread.mode === "agentic"
        ? `Agentic reply: ${content}`
        : `Deep research reply: ${content}`,
    );
    thread.messages.push(userMessage, assistantMessage);
    thread.updated_at = assistantMessage.created_at;

    res.status(200).json({
      thread: summarizeThread(thread),
      user_message: userMessage,
      assistant_message: assistantMessage,
      visible_messages: [userMessage, assistantMessage],
    });
  });

  return router;
}

function getChatStore(input: unknown): Map<string, ChatThreadRecord> {
  if (input instanceof Map) {
    return input as Map<string, ChatThreadRecord>;
  }
  throw new Error("Chat thread store is not configured.");
}

function createThread(mode: ChatMode): ChatThreadRecord {
  const created_at = new Date().toISOString();
  return {
    thread_id: `thread-${randomUUID()}`,
    mode,
    title: null,
    created_at,
    updated_at: created_at,
    messages: [],
  };
}

function summarizeThread(thread: ChatThreadRecord) {
  return {
    thread_id: thread.thread_id,
    mode: thread.mode,
    title: thread.title,
    created_at: thread.created_at,
    updated_at: thread.updated_at,
  };
}

function createMessage(
  threadId: string,
  role: "user" | "assistant",
  content: string,
) {
  return {
    message_id: `msg-${randomUUID()}`,
    thread_id: threadId,
    role,
    content,
    created_at: new Date().toISOString(),
    sources: null,
  };
}
