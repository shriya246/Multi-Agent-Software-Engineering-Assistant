from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.middleware import get_correlation_id
from app.schemas.common import ErrorEnvelope, ErrorPayload

logger = logging.getLogger(__name__)


def build_error_envelope(
    code: str,
    message: str,
    *,
    details: Any | None = None,
    status_code: int = 500,
) -> JSONResponse:
    payload = ErrorEnvelope(
        error=ErrorPayload(
            code=code,
            message=message,
            details=details,
            correlation_id=get_correlation_id(),
        )
    )
    return JSONResponse(status_code=status_code, content=payload.model_dump(mode="json"))


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        logger.info(
            "http_exception",
            extra={"status_code": exc.status_code, "path": request.url.path},
        )
        return build_error_envelope(
            code="http_error",
            message=exc.detail if isinstance(exc.detail, str) else "HTTP request failed",
            details=None if isinstance(exc.detail, str) else exc.detail,
            status_code=exc.status_code,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        logger.info("validation_error", extra={"path": request.url.path})
        return build_error_envelope(
            code="validation_error",
            message="Request validation failed",
            details=exc.errors(),
            status_code=422,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_exception", extra={"path": request.url.path})
        return build_error_envelope(
            code="internal_server_error",
            message="An unexpected error occurred",
            details=None,
            status_code=500,
        )
