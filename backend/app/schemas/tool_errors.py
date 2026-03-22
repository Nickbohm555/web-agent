from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ToolTimings(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    total_ms: int = Field(ge=0)
    provider_ms: Optional[int] = Field(default=None, ge=0)


class ToolMeta(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    operation: str = Field(min_length=1)
    attempts: int = Field(ge=1)
    retries: int = Field(ge=0)
    duration_ms: int = Field(ge=0)
    timings: ToolTimings


class ToolError(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    kind: str = Field(min_length=1)
    message: str = Field(min_length=1)
    retryable: bool
    status_code: Optional[int] = Field(default=None, ge=100, le=599)
    attempt_number: Optional[int] = Field(default=None, ge=1)
    operation: str = Field(min_length=1)
    timings: Optional[ToolTimings] = None

    @model_validator(mode="after")
    def validate_attempt_number(self) -> "ToolError":
        if self.retryable and self.attempt_number is None:
            raise ValueError("attempt_number is required for retryable errors")
        return self


class ToolErrorEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    error: ToolError
    meta: ToolMeta
