from __future__ import annotations

from contextvars import ContextVar
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

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
