from __future__ import annotations


def build_research_plan(topic: str) -> str:
    return (
        "Research plan:\n"
        f"- Define the scope for {topic}\n"
        f"- Compare the leading vendors relevant to {topic}\n"
        f"- Summarize tradeoffs, pricing signals, and open questions for {topic}"
    )
