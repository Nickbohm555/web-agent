const MINIMUM_DETAIL_LENGTH = 60;

const FOLLOW_UP_QUESTIONS = [
  "What exact topic, company, or product should the research focus on?",
  "What decision, deliverable, or final answer do you need from the research?",
  "What constraints matter most, such as timeframe, geography, or sources to prioritize?",
] as const;

export function getDeepResearchFollowUpQuestions(prompt: string): string[] {
  const normalized = prompt.trim();
  if (normalized.length === 0) {
    return [...FOLLOW_UP_QUESTIONS];
  }

  if (isDeepResearchBriefReady(normalized)) {
    return [];
  }

  return [...FOLLOW_UP_QUESTIONS];
}

export function isDeepResearchBriefReady(prompt: string): boolean {
  const normalized = prompt.trim().toLowerCase();
  if (normalized.length < MINIMUM_DETAIL_LENGTH) {
    return false;
  }

  return (
    normalized.includes("topic:") &&
    normalized.includes("goal:") &&
    normalized.includes("constraint")
  );
}

export function buildDeepResearchClarificationMessage(prompt: string): string {
  const questions = getDeepResearchFollowUpQuestions(prompt);
  if (questions.length === 0) {
    return "";
  }

  return [
    "Before I start deep research, answer these follow-up questions:",
    ...questions.map((question, index) => `${index + 1}. ${question}`),
    "",
    "Reply in the same text box using a short brief with `Topic:`, `Goal:`, and `Constraints:` lines.",
  ].join("\n");
}
