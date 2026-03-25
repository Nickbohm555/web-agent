import { describe, expect, it } from "vitest";

import {
  buildDeepResearchClarificationMessage,
  getDeepResearchFollowUpQuestions,
  isDeepResearchBriefReady,
} from "../../frontend/client/deep-research-brief.js";

describe("deep research brief helper", () => {
  it("asks follow-up questions for underspecified prompts", () => {
    expect(getDeepResearchFollowUpQuestions("Research AI")).toEqual([
      "What exact topic, company, or product should the research focus on?",
      "What decision, deliverable, or final answer do you need from the research?",
      "What constraints matter most, such as timeframe, geography, or sources to prioritize?",
    ]);
    expect(isDeepResearchBriefReady("Research AI")).toBe(false);
  });

  it("treats structured briefs as ready to research", () => {
    const prompt = [
      "Topic: OpenAI enterprise roadmap",
      "Goal: compare near-term product priorities",
      "Constraints: use 2025-2026 public sources only",
    ].join("\n");

    expect(getDeepResearchFollowUpQuestions(prompt)).toEqual([]);
    expect(isDeepResearchBriefReady(prompt)).toBe(true);
  });

  it("renders a user-facing clarification message", () => {
    expect(buildDeepResearchClarificationMessage("Research AI")).toContain(
      "Before I start deep research, answer these follow-up questions:",
    );
  });
});
