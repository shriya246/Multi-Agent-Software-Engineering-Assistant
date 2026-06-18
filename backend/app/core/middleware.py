from __future__ import annotations

from contextvars import ContextVar
from typing import Any
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.schemas.common import ErrorEnvelope, ErrorPayload

CORRELATION_ID_HEADER = "X-Request-ID"
_correlation_id_ctx: ContextVar[str] = ContextVar("correlation_id", default="")


def get_correlation_id() -> str:
    value = _correlation_id_ctx.get()
    return value or "unknown"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        request_id = request.headers.get(CORRELATION_ID_HEADER, str(uuid4()))
        token = _correlation_id_ctx.set(request_id)
        try:
            response = await call_next(request)
            response.headers[CORRELATION_ID_HEADER] = request_id
            return response
        finally:
            _correlation_id_ctx.reset(token)


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: Any, *, max_request_size_bytes: int) -> None:
        super().__init__(app)
        self.max_request_size_bytes = max_request_size_bytes

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > self.max_request_size_bytes:
                    payload = ErrorEnvelope(
                        error=ErrorPayload(
                            code="request_too_large",
                            message="Request body exceeds the configured limit",
                            details={"max_request_size_bytes": self.max_request_size_bytes},
                            correlation_id=get_correlation_id(),
                        )
                    )
                    return Response(
                        content=payload.model_dump_json(),
                        status_code=413,
                        media_type="application/json",
                    )
            except ValueError:
                payload = ErrorEnvelope(
                    error=ErrorPayload(
                        code="invalid_request",
                        message="Invalid Content-Length header",
                        details=None,
                        correlation_id=get_correlation_id(),
                    )
                )
                return Response(
                    content=payload.model_dump_json(),
                    status_code=400,
                    media_type="application/json",
                )
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Permissions-Policy", "geolocation=(), microphone=(), camera=()"
        )
        return response
