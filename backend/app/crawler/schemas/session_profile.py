from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _normalize_text(value: str) -> str:
    return value.strip().lower()


class SessionCookie(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    name: str = Field(min_length=1)
    value: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    path: str = "/"
    secure: bool = False
    http_only: bool = False


class StorageSeedEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    name: str = Field(min_length=1)
    value: str = Field(min_length=1)


class DomainSessionMatch(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    hostname: str = Field(min_length=1)
    profile_id: str = Field(min_length=1)


class SessionProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    profile_id: str = Field(min_length=1)
    domains: list[str] = Field(min_length=1)
    cookies: list[SessionCookie] = Field(default_factory=list)
    headers: dict[str, str] = Field(default_factory=dict)
    local_storage: list[StorageSeedEntry] = Field(default_factory=list)
    session_storage: list[StorageSeedEntry] = Field(default_factory=list)
    browser_only: bool = False
    ttl_seconds: Optional[int] = Field(default=None, ge=0)

    @field_validator("profile_id")
    @classmethod
    def normalize_profile_id(cls, value: str) -> str:
        return value.strip()

    @field_validator("domains")
    @classmethod
    def normalize_domains(cls, value: list[str]) -> list[str]:
        return [_normalize_text(item) for item in value]

    def matches(self, hostname: str) -> bool:
        normalized_hostname = _normalize_text(hostname)
        return any(
            normalized_hostname == domain or normalized_hostname.endswith(f".{domain}")
            for domain in self.domains
        )
