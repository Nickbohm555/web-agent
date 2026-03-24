from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


def _strip_text(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("text fields must not be blank")
    return normalized


class QuickEvidenceSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    url: HttpUrl
    excerpt: str = Field(min_length=1)

    @field_validator("source_id", "title", "excerpt")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return _strip_text(value)


class QuickEvidenceBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1)
    sources: list[QuickEvidenceSource] = Field(default_factory=list)

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        return _strip_text(value)


class QuickAnswerSynthesisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1)
    evidence: QuickEvidenceBundle

    @field_validator("question")
    @classmethod
    def normalize_question(cls, value: str) -> str:
        return _strip_text(value)
