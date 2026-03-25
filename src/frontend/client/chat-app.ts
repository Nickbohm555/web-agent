import { threadPathFor, resolveThreadRoute } from "./thread-route.js";
import {
  createChatThread,
  getChatThread,
  postChatMessage,
} from "./chat-api-client.js";
import {
  initialChatState,
  reduceChatState,
  type ChatState,
} from "./chat-state.js";

export function buildChatPageModel(pathname: string) {
  const route = resolveThreadRoute(pathname);
  if (route.kind !== "chat") {
    throw new Error("Chat page route required.");
  }

  return {
    mode: route.mode,
    threadId: route.threadId,
    heading: route.mode === "agentic" ? "Agentic thread" : "Deep research thread",
    postUrl: `/api/chat/threads/${route.threadId}/messages`,
  };
}

export async function startChatApp(windowObject: Window = window): Promise<void> {
  const route = resolveThreadRoute(windowObject.location.pathname);
  if (route.kind !== "chat") {
    return;
  }

  const documentObject = windowObject.document;
  const main = documentObject.querySelector("main");
  if (!(main instanceof HTMLElement)) {
    return;
  }

  let state: ChatState = initialChatState;
  const loadedThread = await getChatThread(route.threadId);
  if (loadedThread.ok) {
    state = reduceChatState(state, { type: "thread_loaded", response: loadedThread.data });
  }

  main.innerHTML = render(state, route.mode);
  const form = documentObject.getElementById("chat-form");
  const input = documentObject.getElementById("chat-input");
  if (!(form instanceof HTMLFormElement) || !(input instanceof HTMLTextAreaElement)) {
    return;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const content = input.value.trim();
    if (!content) {
      return;
    }
    state = reduceChatState(state, { type: "message_post_requested" });
    const response = await postChatMessage(route.threadId, { content }, crypto.randomUUID());
    if (!response.ok) {
      state = reduceChatState(state, { type: "message_failed", message: response.message });
      return;
    }
    state = reduceChatState(state, { type: "message_posted", response: response.data });
    main.innerHTML = render(state, route.mode);
  });
}

export async function launchChatThread(mode: "agentic" | "deep_research"): Promise<string | null> {
  const result = await createChatThread({ mode });
  if (!result.ok) {
    return null;
  }
  return threadPathFor(result.data.thread);
}

function render(state: ChatState, mode: "agentic" | "deep_research"): string {
  const heading = mode === "agentic" ? "Agentic thread" : "Deep research thread";
  const transcript = state.messages.length === 0
    ? "<p>No transcript yet.</p>"
    : state.messages
        .map(
          (message) =>
            `<article><strong>${message.role}</strong><p>${escapeHtml(message.content)}</p></article>`,
        )
        .join("");
  const error = state.error ? `<p>${escapeHtml(state.error)}</p>` : "";

  return `
    <section>
      <h1>${heading}</h1>
      <div>${transcript}</div>
      ${error}
      <form id="chat-form">
        <textarea id="chat-input" placeholder="Send a message"></textarea>
        <button type="submit">Send</button>
      </form>
    </section>
  `;
}

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

if (typeof window !== "undefined") {
  void startChatApp(window);
}
