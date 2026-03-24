from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _normalize_text(value: str) -> str:
    return value.strip()


class SessionCookie(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    name: str = Field(min_length=1)
    value: str
    domain: str = Field(min_length=1)
    path: str = "/"
    secure: bool = False
    http_only: bool = False
    same_site: Optional[Literal["Strict", "Lax", "None"]] = None
    expires: Optional[int] = None

    @field_validator("name", "domain", "path")
    @classmethod
    def normalize_fields(cls, value: str) -> str:
        return _normalize_text(value)


class SessionHeader(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    name: str = Field(min_length=1)
    value: str

    @field_validator("name", "value")
    @classmethod
    def normalize_fields(cls, value: str) -> str:
        return _normalize_text(value)


class StorageSeedEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    key: str = Field(min_length=1)
    value: str

    @field_validator("key", "value")
    @classmethod
    def normalize_fields(cls, value: str) -> str:
        return _normalize_text(value)


class SessionProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: str = Field(min_length=1)
    domains: list[str] = Field(min_length=1)
    cookies: list[SessionCookie] = Field(default_factory=list)
    headers: list[SessionHeader] = Field(default_factory=list)
    local_storage: list[StorageSeedEntry] = Field(default_factory=list)
    session_storage: list[StorageSeedEntry] = Field(default_factory=list)
    browser_only: bool = False
    ttl_seconds: Optional[int] = Field(default=None, ge=1)
    updated_at: Optional[datetime] = None

    @field_validator("id")
    @classmethod
    def normalize_id(cls, value: str) -> str:
        return _normalize_text(value)

    @field_validator("domains")
    @classmethod
    def normalize_domains(cls, value: list[str]) -> list[str]:
        return [_normalize_text(entry).lower() for entry in value]


class DomainSessionMatch(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    matched_domain: str = Field(min_length=1)
    profile: SessionProfile

    @field_validator("matched_domain")
    @classmethod
    def normalize_domain(cls, value: str) -> str:
        return _normalize_text(value).lower()
