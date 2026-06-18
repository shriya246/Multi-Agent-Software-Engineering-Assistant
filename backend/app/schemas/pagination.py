from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class PaginationParams(BaseModel):
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)

    @field_validator("limit")
    @classmethod
    def validate_limit(cls, value: int) -> int:
        if value < 1:
            raise ValueError("limit must be at least 1")
        if value > 100:
            raise ValueError("limit must not exceed 100")
        return value


class PageInfo(BaseModel):
    limit: int
    offset: int
    total: int | None = None
