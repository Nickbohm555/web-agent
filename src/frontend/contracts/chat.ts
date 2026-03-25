export type ChatMode = "agentic" | "deep_research";

export interface ChatThread {
  threadId: string;
  mode: ChatMode;
  title: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface ChatMessage {
  messageId: string;
  threadId: string;
  role: "user" | "assistant";
  content: string;
  createdAt: string;
  sources: Array<{
    sourceId: string;
    title: string;
    url: string;
    snippet: string;
  }> | null;
}

export interface CreateChatThreadRequest {
  mode: ChatMode;
}

export interface CreateChatThreadResponse {
  thread: ChatThread;
}

export interface GetChatThreadResponse {
  thread: ChatThread;
  messages: ChatMessage[];
}

export interface PostChatMessageRequest {
  content: string;
}

export interface PostChatMessageResponse {
  thread: ChatThread;
  userMessage: ChatMessage;
  assistantMessage: ChatMessage;
  visibleMessages: ChatMessage[];
}

interface ChatErrorResponse {
  error: {
    code: string;
    message: string;
  };
}

export function parseCreateChatThreadResponse(input: unknown): CreateChatThreadResponse {
  const record = asRecord(input);
  return {
    thread: parseChatThread(record.thread),
  };
}

export function parseGetChatThreadResponse(input: unknown): GetChatThreadResponse {
  const record = asRecord(input);
  return {
    thread: parseChatThread(record.thread),
    messages: parseChatMessages(record.messages),
  };
}

export function parsePostChatMessageResponse(input: unknown): PostChatMessageResponse {
  const record = asRecord(input);
  return {
    thread: parseChatThread(record.thread),
    userMessage: parseChatMessage(record.user_message),
    assistantMessage: parseChatMessage(record.assistant_message),
    visibleMessages: parseChatMessages(record.visible_messages),
  };
}

export function parseChatError(input: unknown): ChatErrorResponse["error"] {
  const record = asRecord(input);
  const error = asRecord(record.error);
  return {
    code: expectString(error.code, "error.code"),
    message: expectString(error.message, "error.message"),
  };
}

function parseChatThread(input: unknown): ChatThread {
  const record = asRecord(input);
  const mode = expectString(record.mode, "thread.mode");
  if (mode !== "agentic" && mode !== "deep_research") {
    throw new Error("Chat thread mode failed validation.");
  }
  return {
    threadId: expectString(record.thread_id, "thread.thread_id"),
    mode,
    title: record.title === null ? null : expectString(record.title, "thread.title"),
    createdAt: expectString(record.created_at, "thread.created_at"),
    updatedAt: expectString(record.updated_at, "thread.updated_at"),
  };
}

function parseChatMessage(input: unknown): ChatMessage {
  const record = asRecord(input);
  const role = expectString(record.role, "message.role");
  if (role !== "user" && role !== "assistant") {
    throw new Error("Chat message role failed validation.");
  }
  return {
    messageId: expectString(record.message_id, "message.message_id"),
    threadId: expectString(record.thread_id, "message.thread_id"),
    role,
    content: expectString(record.content, "message.content"),
    createdAt: expectString(record.created_at, "message.created_at"),
    sources: parseChatSources(record.sources),
  };
}

function parseChatMessages(input: unknown): ChatMessage[] {
  if (!Array.isArray(input)) {
    throw new Error("Chat messages failed validation.");
  }
  return input.map((message) => parseChatMessage(message));
}

function parseChatSources(input: unknown): ChatMessage["sources"] {
  if (input == null) {
    return null;
  }
  if (!Array.isArray(input)) {
    throw new Error("Chat message sources failed validation.");
  }
  return input.map((source) => {
    const record = asRecord(source);
    return {
      sourceId: expectString(record.source_id, "source.source_id"),
      title: expectString(record.title, "source.title"),
      url: expectString(record.url, "source.url"),
      snippet: expectString(record.snippet, "source.snippet"),
    };
  });
}

function asRecord(input: unknown): Record<string, unknown> {
  if (typeof input !== "object" || input === null || Array.isArray(input)) {
    throw new Error("Chat payload failed validation.");
  }
  return input as Record<string, unknown>;
}

function expectString(input: unknown, field: string): string {
  if (typeof input !== "string" || input.length === 0) {
    throw new Error(`${field} failed validation.`);
  }
  return input;
}
