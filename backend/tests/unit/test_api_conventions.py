from __future__ import annotations

from pydantic import ValidationError

from app.schemas.pagination import PaginationParams


def test_pagination_params_validate_bounds() -> None:
    assert PaginationParams(limit=10, offset=5).limit == 10


def test_pagination_params_reject_invalid_limit() -> None:
    try:
        PaginationParams(limit=0)
    except ValidationError as exc:
        assert "limit" in str(exc)
    else:  # pragma: no cover - defensive branch
        raise AssertionError("expected ValidationError")
