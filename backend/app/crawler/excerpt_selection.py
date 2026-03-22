from __future__ import annotations

import math
import re
from collections import Counter

from backend.app.schemas.web_crawl import WebCrawlExcerpt

MIN_PASSAGE_CHARS = 40
LEXICAL_PREFILTER_LIMIT = 6
MAX_EXCERPTS = 3
LONG_PAGE_RERANK_TEXT_CHARS = 900
MIN_OBJECTIVE_MATCH_SCORE = 0.2
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "about",
    "details",
    "find",
    "for",
    "from",
    "how",
    "into",
    "of",
    "on",
    "or",
    "the",
    "to",
    "what",
    "when",
    "with",
}
TOKEN_PATTERN = re.compile(r"[a-z0-9]+")
MARKDOWN_PREFIX_PATTERN = re.compile(r"^\s{0,3}(?:[#>*-]+|\d+\.)\s*")
PASSAGE_BREAK_PATTERN = re.compile(r"\n\s*\n")


def select_objective_excerpts(
    *,
    text: str,
    markdown: str,
    objective: str | None,
) -> list[WebCrawlExcerpt]:
    if not objective:
        return []

    passages = segment_passages(markdown=markdown, text=text)
    if not passages:
        return []

    scored_passages = score_passages(
        objective=objective,
        passages=passages,
        use_vector_rerank=len(text) >= LONG_PAGE_RERANK_TEXT_CHARS,
    )
    if not scored_passages or scored_passages[0][1] < MIN_OBJECTIVE_MATCH_SCORE:
        return passages[:1]
    return [passage for passage, _score in scored_passages[:MAX_EXCERPTS]]


def segment_passages(*, markdown: str, text: str) -> list[WebCrawlExcerpt]:
    blocks = PASSAGE_BREAK_PATTERN.split(markdown)
    passages: list[WebCrawlExcerpt] = []
    seen_texts: set[str] = set()

    for block in blocks:
        excerpt = build_excerpt(block)
        if excerpt is None:
            continue
        normalized = excerpt.text.casefold()
        if normalized in seen_texts:
            continue
        seen_texts.add(normalized)
        passages.append(excerpt)

    if passages:
        return passages

    fallback_excerpt = build_excerpt(text)
    return [fallback_excerpt] if fallback_excerpt is not None else []


def build_excerpt(block: str) -> WebCrawlExcerpt | None:
    normalized_markdown = normalize_whitespace(block)
    if len(normalized_markdown) < MIN_PASSAGE_CHARS:
        return None

    lines = [
        MARKDOWN_PREFIX_PATTERN.sub("", line).strip()
        for line in block.splitlines()
        if line.strip()
    ]
    normalized_text = normalize_whitespace(" ".join(lines))
    if len(normalized_text) < MIN_PASSAGE_CHARS:
        return None

    return WebCrawlExcerpt(text=normalized_text, markdown=normalized_markdown)


def score_passages(
    *,
    objective: str,
    passages: list[WebCrawlExcerpt],
    use_vector_rerank: bool,
) -> list[tuple[WebCrawlExcerpt, float]]:
    lexical_ranked = sorted(
        (
            (passage, lexical_score(objective=objective, passage=passage.text))
            for passage in passages
        ),
        key=lambda item: item[1],
        reverse=True,
    )
    lexical_prefilter = lexical_ranked[:LEXICAL_PREFILTER_LIMIT]
    if not use_vector_rerank:
        return lexical_prefilter

    return sorted(
        (
            (
                passage,
                (base_score * 0.45) + (cosine_similarity(objective, passage.text) * 0.55),
            )
            for passage, base_score in lexical_prefilter
        ),
        key=lambda item: item[1],
        reverse=True,
    )


def lexical_score(*, objective: str, passage: str) -> float:
    objective_tokens = set(tokenize(objective))
    if not objective_tokens:
        return 0.0

    passage_tokens = Counter(tokenize(passage))
    overlap = objective_tokens.intersection(passage_tokens.keys())
    if not overlap:
        return 0.0

    coverage_score = len(overlap) / len(objective_tokens)
    density_score = sum(passage_tokens[token] for token in overlap) / len(objective_tokens)
    phrase_bonus = 0.2 if normalize_whitespace(objective).casefold() in passage.casefold() else 0.0
    return coverage_score + (density_score * 0.1) + phrase_bonus


def cosine_similarity(left: str, right: str) -> float:
    left_vector = Counter(tokenize(left))
    right_vector = Counter(tokenize(right))
    if not left_vector or not right_vector:
        return 0.0

    dot_product = sum(left_vector[token] * right_vector.get(token, 0) for token in left_vector)
    left_norm = math.sqrt(sum(value * value for value in left_vector.values()))
    right_norm = math.sqrt(sum(value * value for value in right_vector.values()))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot_product / (left_norm * right_norm)


def tokenize(value: str) -> list[str]:
    return [
        token
        for token in TOKEN_PATTERN.findall(value.casefold())
        if len(token) > 2 and token not in STOPWORDS
    ]


def normalize_whitespace(value: str) -> str:
    return " ".join(value.split()).strip()
