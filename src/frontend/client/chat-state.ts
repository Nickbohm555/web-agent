import type {
  ChatMessage,
  ChatThread,
  GetChatThreadResponse,
  PostChatMessageResponse,
} from "../contracts/chat.js";

export interface ChatState {
  thread: ChatThread | null;
  messages: ChatMessage[];
  isPosting: boolean;
  error: string | null;
}

export type ChatAction =
  | { type: "thread_loaded"; response: GetChatThreadResponse }
  | { type: "message_post_requested" }
  | { type: "message_posted"; response: PostChatMessageResponse }
  | { type: "message_failed"; message: string };

export const initialChatState: ChatState = {
  thread: null,
  messages: [],
  isPosting: false,
  error: null,
};

export function reduceChatState(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case "thread_loaded":
      return {
        thread: action.response.thread,
        messages: action.response.messages,
        isPosting: false,
        error: null,
      };
    case "message_post_requested":
      return {
        ...state,
        isPosting: true,
        error: null,
      };
    case "message_posted":
      return {
        thread: action.response.thread,
        messages: [...state.messages, action.response.userMessage, action.response.assistantMessage],
        isPosting: false,
        error: null,
      };
    case "message_failed":
      return {
        ...state,
        isPosting: false,
        error: action.message,
      };
  }
}
