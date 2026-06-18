from __future__ import annotations

from pydantic import BaseModel, Field


class ErrorPayload(BaseModel):
    code: str
    message: str
    correlation_id: str
    details: object | None = None


class ErrorEnvelope(BaseModel):
    error: ErrorPayload


class HealthCheck(BaseModel):
    status: str
    detail: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    status: str
    checks: dict[str, HealthCheck] = Field(default_factory=dict)


class VersionResponse(BaseModel):
    version: str
    environment: str
