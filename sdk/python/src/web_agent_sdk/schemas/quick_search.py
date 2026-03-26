from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class QuickSearchDomainScope(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    include_domains: list[str] = Field(default_factory=list, alias="includeDomains")
    exclude_domains: list[str] = Field(default_factory=list, alias="excludeDomains")


class QuickSearchOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    max_results: int | None = Field(default=None, alias="maxResults", ge=1, le=10)
    timeout_ms: int | None = Field(default=None, alias="timeoutMs", ge=1000, le=10000)
    country: str | None = Field(default=None, min_length=2, max_length=2)
    language: str | None = Field(default=None, min_length=2, max_length=2)
    freshness: str | None = Field(default=None)
    domain_scope: QuickSearchDomainScope | None = Field(default=None, alias="domainScope")


class QuickSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    query: str = Field(min_length=1)
    options: QuickSearchOptions | None = None


class QuickSearchRank(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    position: int = Field(gt=0)
    provider_position: int | None = Field(default=None, alias="providerPosition", gt=0)


class QuickSearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    url: HttpUrl
    snippet: str = ""
    rank: QuickSearchRank


class QuickSearchMetaTimings(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    provider_ms: int | None = Field(default=None, alias="providerMs", ge=0)
    mapping_ms: int | None = Field(default=None, alias="mappingMs", ge=0)


class QuickSearchProviderUsage(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    organic_results: int | None = Field(default=None, alias="organicResults", ge=0)


class QuickSearchUsage(BaseModel):
    model_config = ConfigDict(extra="allow")

    provider: QuickSearchProviderUsage | None = None


class QuickSearchCallMeta(BaseModel):
    model_config = ConfigDict(extra="allow")

    operation: str = Field(min_length=1)
    startedAt: str
    completedAt: str
    durationMs: int = Field(ge=0)
    attempts: int = Field(ge=0)
    retries: int = Field(ge=0)
    cacheHit: bool
    timings: QuickSearchMetaTimings | None = None
    usage: QuickSearchUsage | None = None


class QuickSearchMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    result_count: int = Field(alias="resultCount", ge=0)


class QuickSearchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1)
    results: list[QuickSearchResult]
    meta: QuickSearchCallMeta
    metadata: QuickSearchMetadata
