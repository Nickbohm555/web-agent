import type { ChatMode, ChatThread } from "../contracts/chat.js";

export type ThreadRoute =
  | { kind: "launcher" }
  | { kind: "chat"; mode: ChatMode; threadId: string };

export function resolveThreadRoute(pathname: string): ThreadRoute {
  if (pathname === "/") {
    return { kind: "launcher" };
  }

  const agenticMatch = /^\/agentic\/(?<threadId>[^/]+)$/.exec(pathname);
  if (agenticMatch?.groups?.threadId) {
    return {
      kind: "chat",
      mode: "agentic",
      threadId: agenticMatch.groups.threadId,
    };
  }

  const deepResearchMatch = /^\/deep-research\/(?<threadId>[^/]+)$/.exec(pathname);
  if (deepResearchMatch?.groups?.threadId) {
    return {
      kind: "chat",
      mode: "deep_research",
      threadId: deepResearchMatch.groups.threadId,
    };
  }

  return { kind: "launcher" };
}

export function threadPathFor(thread: ChatThread): string {
  return thread.mode === "agentic"
    ? `/agentic/${thread.threadId}`
    : `/deep-research/${thread.threadId}`;
}
