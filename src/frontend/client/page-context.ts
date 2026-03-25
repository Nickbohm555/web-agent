import type { RunMode } from "../contracts.js";

export interface PageContext {
  mode: RunMode;
  pageTitle: string;
  phaseLabel: string;
  lead: string;
  promptLabel: string;
  threadId: string | null;
}

export function resolvePageContext(pathname: string): PageContext {
  if (pathname.startsWith("/agentic/")) {
    return {
      mode: "agentic",
      pageTitle: "Agentic search",
      phaseLabel: "Agentic Conversation",
      lead: "Continue a bounded search thread with visible evidence and prior context.",
      promptLabel: "Message",
      threadId: pathname.slice("/agentic/".length) || null,
    };
  }

  if (pathname.startsWith("/deep-research/")) {
    return {
      mode: "deep_research",
      pageTitle: "Deep research",
      phaseLabel: "Deep Research",
      lead: "Run longer multi-step research from a dedicated thread page.",
      promptLabel: "Research request",
      threadId: pathname.slice("/deep-research/".length) || null,
    };
  }

  return {
    mode: "quick",
    pageTitle: "Quick search",
    phaseLabel: "Quick Search",
    lead: "Run one fast web-grounded pass from the launcher.",
    promptLabel: "Prompt",
    threadId: null,
  };
}
