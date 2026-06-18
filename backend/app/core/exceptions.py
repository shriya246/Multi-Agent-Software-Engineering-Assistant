"""Custom API exceptions with user-required class names."""

# ruff: noqa: N818

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class AppError(Exception):
    code: str
    message: str
    status_code: int
    details: Any | None = None


class NotFound(AppError):
    def __init__(self, message: str = "Resource not found", *, details: Any | None = None) -> None:
        super().__init__("not_found", message, 404, details)


class Conflict(AppError):
    def __init__(self, message: str = "Conflict", *, details: Any | None = None) -> None:
        super().__init__("conflict", message, 409, details)


class Unauthorized(AppError):
    def __init__(self, message: str = "Unauthorized", *, details: Any | None = None) -> None:
        super().__init__("unauthorized", message, 401, details)


class Forbidden(AppError):
    def __init__(self, message: str = "Forbidden", *, details: Any | None = None) -> None:
        super().__init__("forbidden", message, 403, details)


class InvalidState(AppError):
    def __init__(self, message: str = "Invalid state", *, details: Any | None = None) -> None:
        super().__init__("invalid_state", message, 409, details)


class DependencyUnavailable(AppError):
    def __init__(
        self,
        message: str = "Dependency unavailable",
        *,
        details: Any | None = None,
    ) -> None:
        super().__init__("dependency_unavailable", message, 503, details)


class RateLimited(AppError):
    def __init__(self, message: str = "Rate limited", *, details: Any | None = None) -> None:
        super().__init__("rate_limited", message, 429, details)
